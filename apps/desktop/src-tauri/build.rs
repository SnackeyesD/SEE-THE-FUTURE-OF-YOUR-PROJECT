fn main() {
    #[cfg(windows)]
    {
        use tauri_build::{Attributes, WindowsAttributes};

        // Le manifeste est embarqué dans tous les artefacts du paquet, y compris
        // les binaires de test : sans lui, Windows charge comctl32 v5 et le
        // processus échoue au démarrage en STATUS_ENTRYPOINT_NOT_FOUND.
        let attributes =
            Attributes::new().windows_attributes(WindowsAttributes::new_without_app_manifest());
        tauri_build::try_build(attributes).expect("tauri-build a échoué");
        println!("cargo:rerun-if-changed=app-resource.rc");
        println!("cargo:rerun-if-changed=app.manifest");
        embed_resource::compile_for_everything("app-resource.rc", embed_resource::NONE)
            .manifest_required()
            .expect("compilation de la ressource Windows");
    }
    #[cfg(not(windows))]
    tauri_build::build();
}
