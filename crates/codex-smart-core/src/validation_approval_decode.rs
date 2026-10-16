//! Offline canonical envelope v1 decoding (#139). No authentication or admission.
//! All supplied identities and digest fields remain attacker assertions. This module
//! has no runtime caller and cannot construct validation-policy approval evidence.
use sha2::{Digest, Sha256};

const DOMAIN: &[u8] = b"codex-smart/validation-approval-envelope/v1\0";
const MAX_ENVELOPE: usize = 16_384;
const MAX_COMBINED: usize = 65_536;

/// Fixed diagnostics deliberately carry no input bytes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Diagnostic {
    Oversize,
    Truncated,
    UnsupportedDomain,
    UnsupportedVersion,
    UnknownField,
    DuplicateField,
    OutOfOrder,
    TrailingPayload,
    MissingField,
    MalformedValue,
    UnsupportedSchema,
    UnsupportedProofSuite,
}
use Diagnostic::*;

/// Format-only result. Unkeyed hashes establish neither authenticity nor rights.
/// No Debug/Display/serialization or conversion to an approval is provided.
pub struct ParseOnly {
    pub spec_digest: [u8; 32],
    pub body_digest: [u8; 32],
    pub wire_digest: [u8; 32],
}
impl ParseOnly {
    pub const fn admitted(&self) -> bool {
        false
    }
    pub const fn attested(&self) -> bool {
        false
    }
    pub const fn runtime_ready(&self) -> bool {
        false
    }
    pub const fn execution_authorized(&self) -> bool {
        false
    }
}

fn hash(domain: &[u8], bytes: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(domain);
    h.update([0]);
    h.update(bytes);
    h.finalize().into()
}

struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}
impl<'a> Reader<'a> {
    fn take(&mut self, count: usize) -> Result<&'a [u8], Diagnostic> {
        let end = self.pos.checked_add(count).ok_or(Truncated)?;
        let raw = self.bytes.get(self.pos..end).ok_or(Truncated)?;
        self.pos = end;
        Ok(raw)
    }
    fn byte(&mut self) -> Result<u8, Diagnostic> {
        Ok(self.take(1)?[0])
    }
    fn short(&mut self) -> Result<u16, Diagnostic> {
        let v = self.take(2)?;
        Ok(u16::from_be_bytes([v[0], v[1]]))
    }
    fn string(&mut self, cap: usize) -> Result<&'a [u8], Diagnostic> {
        let size = usize::from(self.short()?);
        if size > cap {
            return Err(MalformedValue);
        }
        let v = self.take(size)?;
        text(v, cap)?;
        Ok(v)
    }
}
fn text(v: &[u8], cap: usize) -> Result<(), Diagnostic> {
    if v.is_empty() || v.len() > cap || !v.iter().all(|b| (33..=126).contains(b)) {
        return Err(MalformedValue);
    }
    Ok(())
}
fn identity(v: &[u8], size: usize) -> Result<(), Diagnostic> {
    if v.len() != size || v.iter().all(|b| *b == 0) {
        return Err(MalformedValue);
    }
    Ok(())
}
fn label(v: &[u8]) -> bool {
    (1..=64).contains(&v.len())
        && v.iter()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b"_.-".contains(b))
}
fn specification(bytes: &[u8]) -> Result<(), Diagnostic> {
    let mut r = Reader { bytes, pos: 0 };
    if r.short()? != crate::validation_policy::SCHEMA_V1 {
        return Err(UnsupportedSchema);
    }
    r.string(1024)?;
    identity(r.take(32)?, 32)?;
    for _ in 0..3 {
        r.take(4)?;
    }
    for _ in 0..2 {
        identity(r.take(32)?, 32)?;
    }
    let argc = r.byte()?;
    if argc > 32 {
        return Err(MalformedValue);
    }
    let mut used = 0usize;
    for _ in 0..argc {
        let kind = r.byte()?;
        if !(1..=3).contains(&kind) {
            return Err(MalformedValue);
        }
        let arg = r.string(if kind == 3 { 1024 } else { 4096 })?;
        used = used.checked_add(arg.len()).ok_or(MalformedValue)?;
        if used > 4096 {
            return Err(MalformedValue);
        }
    }
    r.string(1024)?;
    r.string(1024)?;
    if !(1..=10).contains(&r.byte()?) {
        return Err(MalformedValue);
    }
    for _ in 0..6 {
        r.take(8)?;
    }
    if !(1..=3).contains(&r.byte()?) {
        return Err(MalformedValue);
    }
    if !(1..=2).contains(&r.byte()?) || r.pos != bytes.len() {
        return Err(MalformedValue);
    }
    Ok(())
}

/// Decode bounded canonical bytes only. External inputs count toward the size
/// gate but are never interpreted as proof or policy. No allocations or I/O.
pub fn decode(
    envelope: &[u8],
    external_proof: &[u8],
    independent_policy: &[u8],
) -> Result<ParseOnly, Diagnostic> {
    if envelope.len() > MAX_ENVELOPE
        || external_proof.len() > MAX_COMBINED
        || independent_policy.len() > MAX_COMBINED
        || envelope
            .len()
            .checked_add(external_proof.len())
            .and_then(|n| n.checked_add(independent_policy.len()))
            .is_none_or(|n| n > MAX_COMBINED)
    {
        return Err(Oversize);
    }
    let mut r = Reader {
        bytes: envelope,
        pos: 0,
    };
    if r.take(DOMAIN.len())? != DOMAIN {
        return Err(UnsupportedDomain);
    }
    if r.short()? != 1 {
        return Err(UnsupportedVersion);
    }
    let mut fields: [Option<&[u8]>; 26] = [None; 26];
    let mut last = 0;
    let mut body_end = 0;
    while r.pos < envelope.len() {
        if last == 26 {
            return Err(TrailingPayload);
        }
        let start = r.pos;
        let header = r.take(3)?;
        let tag = header[0];
        if !(1..=26).contains(&tag) {
            return Err(UnknownField);
        }
        let slot = &mut fields[usize::from(tag - 1)];
        if slot.is_some() {
            return Err(DuplicateField);
        }
        if tag < last {
            return Err(OutOfOrder);
        }
        *slot = Some(r.take(usize::from(u16::from_be_bytes([header[1], header[2]])))?);
        last = tag;
        if tag == 26 {
            body_end = start;
        }
    }
    if fields.iter().any(Option::is_none) {
        return Err(MissingField);
    }
    // The complete framing pass above proves every slot present.
    let fields = fields.map(|v| v.unwrap_or_default());
    for (index, v) in fields.iter().enumerate() {
        let tag = index + 1;
        match tag {
            1 if !matches!(*v, [1] | [2]) => return Err(MalformedValue),
            3 if *v != [1] => return Err(MalformedValue),
            2 | 4 | 5 => {
                text(
                    v,
                    match tag {
                        2 => 129,
                        4 => 1024,
                        _ => 64,
                    },
                )?;
                if tag == 2 {
                    let mut parts = v.split(|b| *b == b'/');
                    if !parts.next().is_some_and(label)
                        || !parts.next().is_some_and(label)
                        || parts.next().is_some()
                    {
                        return Err(MalformedValue);
                    }
                }
                if tag == 5 && !label(v) {
                    return Err(MalformedValue);
                }
            }
            6 | 10 | 11 | 16 | 17 => {
                if v.len() != 8 {
                    return Err(MalformedValue);
                }
                if matches!(tag, 6 | 10) {
                    identity(v, 8)?;
                }
            }
            7..=9 | 19..=24 => identity(v, 32)?,
            12..=15 => identity(v, 16)?,
            18 => specification(v)?,
            25 if v.len() != 2 => return Err(MalformedValue),
            26 if v.len() > 4096 => return Err(MalformedValue),
            _ => {}
        }
    }
    if fields[24] != [0, 0] {
        return Err(UnsupportedProofSuite);
    }
    if !fields[25].is_empty() {
        return Err(MalformedValue);
    }
    // Re-encode the validated, uniquely represented values in fixed storage.
    // S has fixed-width integers and length-prefixed ASCII only; its validated
    // byte representation has no alternate spellings or optional members.
    let mut canonical = [0u8; MAX_ENVELOPE];
    let mut pos = 0;
    for piece in [DOMAIN, &[0, 1]] {
        canonical[pos..pos + piece.len()].copy_from_slice(piece);
        pos += piece.len();
    }
    for (i, v) in fields.iter().enumerate() {
        canonical[pos] = (i + 1) as u8;
        canonical[pos + 1..pos + 3].copy_from_slice(&(v.len() as u16).to_be_bytes());
        pos += 3;
        canonical[pos..pos + v.len()].copy_from_slice(v);
        pos += v.len();
    }
    if &canonical[..pos] != envelope {
        return Err(MalformedValue);
    }
    Ok(ParseOnly {
        spec_digest: hash(b"codex-smart/validation-specification/v1", fields[17]),
        body_digest: hash(
            b"codex-smart/validation-approval-body/v1",
            &envelope[..body_end],
        ),
        wire_digest: hash(b"codex-smart/validation-approval-wire/v1", envelope),
    })
}

#[cfg(test)]
mod tests;
