//! Version 1 bounded inspection-only wire protocol; payloads deliberately lack Debug.
use crate::{
    playbook::{ContextObligation, builtin},
    preparation::{Failure, Limits, Preparation, Request, Snippet},
    routing::{
        assessment::{RoutingFacts, TaskKind, assess},
        engine::CapabilitySurface,
    },
    workflow::{NativeSurface, ResourceCatalog, WorkflowPlan, plan_workflow},
};
use sha2::{Digest, Sha256};
use std::{
    io::{Read, Write},
    path::PathBuf,
    time::Duration,
};

pub const VERSION: u8 = 1;
pub const MAX_REQUEST: usize = 18432;
pub const MAX_RESPONSE: usize = 65536;
const REQUEST: &[u8; 8] = b"CSPREQ\0\x01";
const RESPONSE: &[u8; 8] = b"CSPRES\0\x01";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct InvalidMessage;
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Intent {
    Inspection,
}
/// Only inspection/relevant-file nominations are accepted in this initial slice.
pub struct PreparationRequest {
    pub root: PathBuf,
    pub intent: Intent,
    pub files: Vec<Request>,
    pub limits: Limits,
}
pub(crate) fn plan() -> WorkflowPlan {
    plan_workflow(
        &assess(&RoutingFacts {
            known_operations: vec![TaskKind::Inspect],
            ..Default::default()
        }),
        None,
        &NativeSurface::default(),
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    )
}
impl PreparationRequest {
    pub fn validate(&self) -> Result<(), InvalidMessage> {
        let l = self.limits;
        if !l.valid()
            || !l.elapsed.subsec_nanos().is_multiple_of(1_000_000)
            || self.files.len() > l.files
            || !self.root.is_absolute()
        {
            return Err(InvalidMessage);
        }
        let root = self.root.to_str().ok_or(InvalidMessage)?;
        if root.len() > 1024 || !crate::preparation::safe_root(&self.root) {
            return Err(InvalidMessage);
        }
        let mut paths = std::collections::BTreeSet::new();
        for file in &self.files {
            if file.obligation != ContextObligation::RelevantFiles
                || !crate::preparation::safe_nomination(&file.path)
                || file.path.to_str().is_none()
                || !paths.insert(&file.path)
            {
                return Err(InvalidMessage);
            }
        }
        Ok(())
    }
    pub fn encode(&self) -> Result<Vec<u8>, InvalidMessage> {
        self.validate()?;
        let mut payload = vec![1]; // typed inspection intent
        string(&mut payload, self.root.to_str().ok_or(InvalidMessage)?)?;
        for n in [
            self.limits.files,
            self.limits.file_bytes,
            self.limits.total_bytes,
            self.limits.elapsed.as_millis() as usize,
            self.files.len(),
        ] {
            payload.extend_from_slice(&(n as u32).to_be_bytes());
        }
        for file in &self.files {
            payload.push(1); // RelevantFiles
            string(&mut payload, file.path.to_str().ok_or(InvalidMessage)?)?;
        }
        frame(REQUEST, payload, MAX_REQUEST)
    }
    pub fn decode(bytes: &[u8]) -> Result<Self, InvalidMessage> {
        let mut c = Cursor(unframe(bytes, REQUEST, MAX_REQUEST)?);
        if c.byte()? != 1 {
            return Err(InvalidMessage);
        }
        let root = c.string(1024)?.into();
        let limits = Limits {
            files: c.number()?,
            file_bytes: c.number()?,
            total_bytes: c.number()?,
            elapsed: Duration::from_millis(c.number()? as u64),
        };
        let count = c.number()?;
        if count > 16 {
            return Err(InvalidMessage);
        }
        let mut files = Vec::with_capacity(count);
        for _ in 0..count {
            if c.byte()? != 1 {
                return Err(InvalidMessage);
            }
            files.push(Request {
                path: c.string(1024)?.into(),
                obligation: ContextObligation::RelevantFiles,
            });
        }
        c.end()?;
        let request = Self {
            root,
            intent: Intent::Inspection,
            files,
            limits,
        };
        request.validate()?;
        Ok(request)
    }
}
fn string(bytes: &mut Vec<u8>, s: &str) -> Result<(), InvalidMessage> {
    if s.contains('\0') {
        return Err(InvalidMessage);
    }
    let len = u32::try_from(s.len()).map_err(|_| InvalidMessage)?;
    bytes.extend_from_slice(&len.to_be_bytes());
    bytes.extend_from_slice(s.as_bytes());
    Ok(())
}
fn frame(magic: &[u8; 8], payload: Vec<u8>, max: usize) -> Result<Vec<u8>, InvalidMessage> {
    if payload.len() + 12 > max {
        return Err(InvalidMessage);
    }
    let mut bytes = magic.to_vec();
    bytes.extend_from_slice(&(payload.len() as u32).to_be_bytes());
    bytes.extend(payload);
    Ok(bytes)
}
fn unframe<'a>(bytes: &'a [u8], magic: &[u8; 8], max: usize) -> Result<&'a [u8], InvalidMessage> {
    if bytes.len() < 12 || bytes.len() > max || &bytes[..8] != magic {
        return Err(InvalidMessage);
    }
    let len = u32::from_be_bytes(bytes[8..12].try_into().map_err(|_| InvalidMessage)?) as usize;
    if len != bytes.len() - 12 {
        return Err(InvalidMessage);
    }
    Ok(&bytes[12..])
}
struct Cursor<'a>(&'a [u8]);
impl<'a> Cursor<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], InvalidMessage> {
        if n > self.0.len() {
            return Err(InvalidMessage);
        }
        let (a, b) = self.0.split_at(n);
        self.0 = b;
        Ok(a)
    }
    fn byte(&mut self) -> Result<u8, InvalidMessage> {
        Ok(self.take(1)?[0])
    }
    fn number(&mut self) -> Result<usize, InvalidMessage> {
        Ok(u32::from_be_bytes(self.take(4)?.try_into().map_err(|_| InvalidMessage)?) as usize)
    }
    fn string(&mut self, max: usize) -> Result<&'a str, InvalidMessage> {
        let len = self.number()?;
        if len > max {
            return Err(InvalidMessage);
        }
        let s = std::str::from_utf8(self.take(len)?).map_err(|_| InvalidMessage)?;
        if s.contains('\0') {
            return Err(InvalidMessage);
        }
        Ok(s)
    }
    fn end(self) -> Result<(), InvalidMessage> {
        if self.0.is_empty() {
            Ok(())
        } else {
            Err(InvalidMessage)
        }
    }
}
const FAILURES: &[Failure] = &[
    Failure::InvalidLimits,
    Failure::MissingIntent,
    Failure::BlockedPlan,
    Failure::InvalidRequest,
    Failure::UnsafeOrMissingFile,
    Failure::FileLimit,
    Failure::ByteLimit,
    Failure::Deadline,
    Failure::InvalidText,
    Failure::UnsupportedPlatform,
];
fn response(request: &[u8], result: Preparation) -> Result<Vec<u8>, InvalidMessage> {
    let mut payload = Sha256::digest(request).to_vec();
    payload.push(match result.failure {
        None => 0,
        Some(f) => {
            1 + FAILURES
                .iter()
                .position(|x| *x == f)
                .ok_or(InvalidMessage)? as u8
        }
    });
    payload.extend_from_slice(&(result.snippets.len() as u32).to_be_bytes());
    for snippet in result.snippets {
        string(
            &mut payload,
            snippet.request.path.to_str().ok_or(InvalidMessage)?,
        )?;
        string(&mut payload, &snippet.text)?;
        payload.extend_from_slice(&Sha256::digest(snippet.text.as_bytes()));
    }
    frame(RESPONSE, payload, MAX_RESPONSE)
}
pub(crate) fn verify_response(
    bytes: &[u8],
    request: &PreparationRequest,
    encoded: &[u8],
) -> Result<Preparation, InvalidMessage> {
    let mut c = Cursor(unframe(bytes, RESPONSE, MAX_RESPONSE)?);
    if c.take(32)? != Sha256::digest(encoded).as_slice() {
        return Err(InvalidMessage);
    }
    let code = c.byte()?;
    let failure = if code == 0 {
        None
    } else {
        Some(*FAILURES.get(code as usize - 1).ok_or(InvalidMessage)?)
    };
    let count = c.number()?;
    if count > request.files.len()
        || (failure.is_some() && count != 0)
        || (failure.is_none() && count != request.files.len())
    {
        return Err(InvalidMessage);
    }
    let plan = plan();
    let mut result = Preparation {
        validation: plan.validation_recipe(&NativeSurface::default()),
        failure,
        unresolved: builtin(plan.selection.archetype.ok_or(InvalidMessage)?)
            .context
            .iter()
            .copied()
            .collect(),
        snippets: Vec::with_capacity(count),
    };
    let mut ordered: Vec<_> = request.files.iter().collect();
    ordered.sort_by(|a, b| a.path.cmp(&b.path));
    let mut total = 0;
    for nomination in ordered.into_iter().take(count) {
        if c.string(1024)? != nomination.path.to_str().ok_or(InvalidMessage)? {
            return Err(InvalidMessage);
        }
        let text = c.string(request.limits.file_bytes)?.to_owned();
        total += text.len();
        if total > request.limits.total_bytes {
            return Err(InvalidMessage);
        }
        let digest = Sha256::digest(text.as_bytes());
        if c.take(32)? != digest.as_slice() {
            return Err(InvalidMessage);
        }
        result.snippets.push(Snippet {
            request: nomination.clone(),
            text,
            sha256: digest.iter().map(|b| format!("{b:02x}")).collect(),
        });
    }
    c.end()?;
    Ok(result)
}
/// Dedicated worker only: one length-bounded frame plus EOF, no logs or commands.
pub fn serve(input: impl Read, mut output: impl Write) -> Result<(), InvalidMessage> {
    let mut bytes = Vec::new();
    input
        .take(MAX_REQUEST as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| InvalidMessage)?;
    let request = PreparationRequest::decode(&bytes)?;
    let result = crate::preparation::prepare(
        &request.root,
        &plan(),
        &NativeSurface::default(),
        &request.files,
        request.limits,
    );
    output
        .write_all(&response(&bytes, result)?)
        .map_err(|_| InvalidMessage)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request() -> PreparationRequest {
        PreparationRequest {
            root: "/tmp/public-project".into(),
            intent: Intent::Inspection,
            files: vec![Request {
                path: "a.rs".into(),
                obligation: ContextObligation::RelevantFiles,
            }],
            limits: Limits::default(),
        }
    }
    #[test]
    fn strict_request_roundtrip_and_limits() {
        let r = request();
        let encoded = r.encode().unwrap();
        assert_eq!(
            PreparationRequest::decode(&encoded)
                .unwrap()
                .encode()
                .unwrap(),
            encoded
        );
        for n in 0..encoded.len() {
            assert!(PreparationRequest::decode(&encoded[..n]).is_err());
        }
        let mut oversized = encoded.clone();
        oversized[8..12].copy_from_slice(&u32::MAX.to_be_bytes());
        assert!(PreparationRequest::decode(&oversized).is_err());
        let mut r = request();
        r.files.push(r.files[0].clone());
        assert!(r.encode().is_err());
        let mut r = request();
        r.files[0].obligation = ContextObligation::ReleaseState;
        assert!(r.encode().is_err());
        let mut r = request();
        r.limits.elapsed = Duration::from_nanos(1);
        assert!(r.encode().is_err());
    }
    #[test]
    fn exact_response_binding_snippets_and_ceiling() {
        let r = request();
        let encoded = r.encode().unwrap();
        let result = Preparation {
            snippets: vec![Snippet {
                request: r.files[0].clone(),
                text: "public text".into(),
                sha256: String::new(),
            }],
            ..Default::default()
        };
        let wire = response(&encoded, result).unwrap();
        let got = verify_response(&wire, &r, &encoded).unwrap();
        assert_eq!(got.snippets[0].text, "public text");
        for n in 0..wire.len() {
            assert!(verify_response(&wire[..n], &r, &encoded).is_err());
        }
        for i in [7, 12, 44, 48, 56, wire.len() - 1] {
            let mut changed = wire.clone();
            changed[i] ^= 255;
            assert!(verify_response(&changed, &r, &encoded).is_err());
        }
        let mut lowered = request();
        lowered.limits.total_bytes = 1;
        assert!(verify_response(&wire, &lowered, &encoded).is_err());
    }
}
