use codex_smart_core::{
    config::{Layer, Origin},
    migration::upgraded,
};
use toml_edit::DocumentMut;

#[test]
fn migration_preserves_comments_and_opaque_quoted_keys() {
    let source = "# header\nkind = 'codex-smart'\nschema_version = 0 # schema\n# effort\nreasoning_effort = 'medium' # selected\n\n[extensions.'team.name']\n'key with spaces' = { date = 2026-10-15, text = 'unchanged' } # opaque\n";
    let output = upgraded(source).unwrap();
    Layer::parse(&output, Origin::User).unwrap();
    for comment in ["# header", "# schema", "# effort", "# selected", "# opaque"] {
        assert_eq!(output.matches(comment).count(), 1);
    }
    let before = source.parse::<DocumentMut>().unwrap();
    let after = output.parse::<DocumentMut>().unwrap();
    assert_eq!(
        before["extensions"].to_string(),
        after["extensions"].to_string()
    );
    assert_eq!(after["reasoning"].as_str(), Some("medium"));
    assert!(!after.contains_key("reasoning_effort"));
    assert_eq!(upgraded(&output).unwrap(), output);
}

#[test]
fn roundtrip_keeps_comments_unicode_dotted_keys_and_datetime() {
    let source = "# comment\n'key.with.dot' = '雪' # inline\nwhen = 2026-10-15T01:02:03Z\n[table]\nvalue = [1, 2, 3]\n";
    let doc = source.parse::<DocumentMut>().unwrap();
    assert_eq!(doc.to_string(), source);
    let reparsed = doc.to_string().parse::<DocumentMut>().unwrap();
    assert_eq!(reparsed["key.with.dot"].as_str(), Some("雪"));
    assert!(reparsed["when"].as_datetime().is_some());
}

#[test]
fn malformed_input_fails_closed_without_panicking() {
    for suffix in [
        "x = 1\nx = 2\n",
        "x = [1,\n",
        "x = '\n",
        "[unterminated\n",
        "x = 2026-99-99\n",
        "x = \"\\uD800\"\n",
    ] {
        let source = format!("kind = 'codex-smart'\nschema_version = 0\n{suffix}");
        assert!(source.parse::<DocumentMut>().is_err());
        assert!(upgraded(&source).is_err());
    }
}

#[test]
fn generated_keys_are_quoted_and_reparse_as_single_keys() {
    let mut doc = DocumentMut::new();
    for key in ["a.b", "with space", "quote\"key", "line\nbreak", "雪"] {
        doc[key] = toml_edit::value("safe");
    }
    let output = doc.to_string();
    let parsed = output.parse::<DocumentMut>().unwrap();
    for (key, _) in doc.iter() {
        assert_eq!(parsed[key].as_str(), Some("safe"));
    }
    assert_eq!(parsed.len(), doc.len());
}
