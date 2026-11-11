use keyring::Entry;

const SERVICE: &str = "see-the-future";
const PREFIX: &str = "seefuture:";
const MAX_REF_LENGTH: usize = 200;

pub fn validate_reference(reference: &str) -> Result<(), String> {
    if !reference.starts_with(PREFIX) {
        return Err("référence de trousseau invalide".into());
    }
    if reference.len() > MAX_REF_LENGTH {
        return Err("référence de trousseau trop longue".into());
    }
    if reference.chars().any(|character| character.is_control()) {
        return Err("référence de trousseau invalide".into());
    }
    Ok(())
}

fn entry(reference: &str) -> Result<Entry, String> {
    validate_reference(reference)?;
    Entry::new(SERVICE, reference).map_err(|error| format!("trousseau indisponible: {error}"))
}

pub fn set_secret(reference: &str, secret: &str) -> Result<(), String> {
    if secret.trim().is_empty() {
        return Err("clé API vide".into());
    }
    entry(reference)?
        .set_password(secret)
        .map_err(|error| format!("écriture du trousseau impossible: {error}"))
}

pub fn get_secret(reference: &str) -> Result<Option<String>, String> {
    match entry(reference)?.get_password() {
        Ok(secret) => Ok(Some(secret)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(error) => Err(format!("lecture du trousseau impossible: {error}")),
    }
}

pub fn delete_secret(reference: &str) -> Result<(), String> {
    match entry(reference)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(error) => Err(format!("suppression dans le trousseau impossible: {error}")),
    }
}

#[cfg(test)]
mod tests {
    use super::validate_reference;
    use keyring::credential::CredentialPersistence;

    #[test]
    fn uses_a_persistent_platform_store() {
        assert!(matches!(
            keyring::default::default_credential_builder().persistence(),
            CredentialPersistence::UntilDelete
        ));
    }

    #[test]
    fn rejects_references_outside_the_application_namespace() {
        assert!(validate_reference("other:key").is_err());
        assert!(validate_reference("seefuture:\n").is_err());
        assert!(validate_reference(&format!("seefuture:{}", "a".repeat(300))).is_err());
        assert!(validate_reference("seefuture:project:profile").is_ok());
    }
}
