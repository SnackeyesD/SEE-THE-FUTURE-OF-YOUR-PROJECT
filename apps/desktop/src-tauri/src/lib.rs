mod keychain;
mod sidecar;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use serde_json::{json, Value};
use sidecar::{SidecarManager, SidecarStatus};
use tauri::{Emitter, Manager};

static SHUTTING_DOWN: AtomicBool = AtomicBool::new(false);

fn start_supervisor(handle: tauri::AppHandle) {
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(2));
        if SHUTTING_DOWN.load(Ordering::SeqCst) {
            break;
        }

        let state = handle.state::<Mutex<SidecarManager>>();
        let locked = state.lock();
        if let Ok(mut manager) = locked {
            if manager.supervision_enabled() && !manager.status().running {
                if let Err(error) = manager.ensure_running() {
                    eprintln!("[sidecar] redémarrage automatique impossible: {error}");
                }
            }
        }
    });
}

#[tauri::command]
fn sidecar_status(state: tauri::State<'_, Mutex<SidecarManager>>) -> Result<SidecarStatus, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    Ok(manager.status())
}

#[tauri::command]
fn sidecar_health(state: tauri::State<'_, Mutex<SidecarManager>>) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("health", json!({}))
}

#[tauri::command]
fn sidecar_ping(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    echo: Option<String>,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    let params = match echo {
        Some(echo) => json!({ "echo": echo }),
        None => json!({}),
    };
    manager.request("ping", params)
}

fn inject_api_key(params: Value) -> Result<Value, String> {
    let reference = params
        .get("profile")
        .and_then(|profile| profile.get("keychainRef"))
        .and_then(Value::as_str);
    let key = match reference {
        Some(reference) if !reference.is_empty() => keychain::get_secret(reference)?
            .ok_or_else(|| "clé API absente du trousseau".to_string())?,
        _ => return Ok(params),
    };
    let mut object = params
        .as_object()
        .cloned()
        .ok_or_else(|| "paramètres fournisseur invalides".to_string())?;
    object.insert("apiKey".into(), Value::String(key));
    Ok(Value::Object(object))
}

const AGENT_METHODS: &[&str] = &[
    "agent.state",
    "agent.start",
    "agent.reset",
    "agent.permission.list",
    "agent.permission.set",
    "agent.permission.delete",
    "agent.trace",
    "agent.trace.export",
    "agent.tools",
];

const PROVIDER_METHODS: &[&str] = &[
    "provider.catalog",
    "provider.profile.list",
    "provider.profile.save",
    "provider.role.list",
    "provider.role.set",
    "provider.role.delete",
    "provider.usage",
    "provider.budget.get",
    "provider.budget.set",
    "provider.budget.delete",
];

const SANDBOX_METHODS: &[&str] = &[
    "sandbox.analyze",
    "sandbox.audit.record",
    "sandbox.audit.list",
    "sandbox.audit.export",
];

#[tauri::command]
fn project_list(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    include_archived: Option<bool>,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request(
        "project.list",
        json!({ "includeArchived": include_archived.unwrap_or(false) }),
    )
}

#[tauri::command]
fn project_create(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    name: String,
    description: Option<String>,
    currency: Option<String>,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request(
        "project.create",
        json!({
            "name": name,
            "description": description.unwrap_or_default(),
            "currency": currency.unwrap_or_else(|| "XOF".into()),
        }),
    )
}

#[tauri::command]
fn project_data(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("project.data", params)
}

#[tauri::command]
fn project_brief_save(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("project.brief.save", params)
}

#[tauri::command]
fn project_scenario_save(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("project.scenario.save", params)
}

#[tauri::command]
fn project_simulate(
    app: tauri::AppHandle,
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request_with("project.simulate", params, |message| {
        if message.get("method").and_then(Value::as_str) == Some("simulate.progress") {
            let payload = message.get("params").cloned().unwrap_or_else(|| json!({}));
            let _ = app.emit("simulation:progress", payload);
        }
    })
}

#[tauri::command]
fn provider_call(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    if !PROVIDER_METHODS.contains(&method.as_str()) {
        return Err(format!("méthode fournisseur non autorisée: {method}"));
    }
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request(&method, params)
}

#[tauri::command]
fn agent_call(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    if !AGENT_METHODS.contains(&method.as_str()) {
        return Err(format!("méthode agent non autorisée: {method}"));
    }
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request(&method, params)
}

#[tauri::command]
fn agent_turn(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let project_id = params
        .get("projectId")
        .and_then(Value::as_str)
        .ok_or_else(|| "projectId manquant".to_string())?;
    let mut prepare = json!({ "projectId": project_id });
    if let Some(role) = params.get("role") {
        prepare["role"] = role.clone();
    }

    let mut manager = state.lock().map_err(|error| error.to_string())?;
    let prepared = manager.request("agent.prepare", prepare)?;
    let mut object = params
        .as_object()
        .cloned()
        .ok_or_else(|| "paramètres d'agent invalides".to_string())?;
    let profile = prepared
        .get("profile")
        .cloned()
        .ok_or_else(|| "profil fournisseur absent de la préparation".to_string())?;
    let role = prepared
        .get("role")
        .cloned()
        .ok_or_else(|| "rôle absent de la préparation".to_string())?;
    object.insert("profile".into(), profile);
    object.insert("role".into(), role);
    let params = inject_api_key(Value::Object(object))?;
    manager.request("agent.turn", params)
}

#[tauri::command]
fn sandbox_call(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    if !SANDBOX_METHODS.contains(&method.as_str()) {
        return Err(format!("méthode sandbox non autorisée: {method}"));
    }
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request(&method, params)
}

#[tauri::command]
fn provider_key_set(keychain_ref: String, secret: String) -> Result<(), String> {
    keychain::set_secret(&keychain_ref, &secret)
}

#[tauri::command]
fn provider_key_status(keychain_ref: String) -> Result<bool, String> {
    Ok(keychain::get_secret(&keychain_ref)?.is_some())
}

#[tauri::command]
fn provider_key_delete(keychain_ref: String) -> Result<(), String> {
    keychain::delete_secret(&keychain_ref)
}

#[tauri::command]
fn provider_profile_save(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("provider.profile.save", params)
}

#[tauri::command]
fn provider_profile_delete(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    project_id: String,
    profile_id: String,
) -> Result<Value, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    let listing = manager.request("provider.profile.list", json!({ "projectId": project_id }))?;
    if let Some(reference) = listing
        .get("profiles")
        .and_then(Value::as_array)
        .and_then(|profiles| {
            profiles.iter().find(|profile| {
                profile.get("id").and_then(Value::as_str) == Some(profile_id.as_str())
            })
        })
        .and_then(|profile| profile.get("keychainRef"))
        .and_then(Value::as_str)
    {
        keychain::delete_secret(reference)?;
    }
    manager.request(
        "provider.profile.delete",
        json!({ "profileId": profile_id }),
    )
}

#[tauri::command]
fn provider_test(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let params = inject_api_key(params)?;
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("provider.test", params)
}

#[tauri::command]
fn provider_models(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let params = inject_api_key(params)?;
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("provider.models", params)
}

#[tauri::command]
fn provider_chat(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let params = inject_api_key(params)?;
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.request("provider.chat", params)
}

#[tauri::command]
fn sidecar_restart(
    state: tauri::State<'_, Mutex<SidecarManager>>,
) -> Result<SidecarStatus, String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    Ok(manager.restart())
}

#[tauri::command]
fn sidecar_shutdown(state: tauri::State<'_, Mutex<SidecarManager>>) -> Result<(), String> {
    let mut manager = state.lock().map_err(|error| error.to_string())?;
    manager.shutdown();
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .manage(Mutex::new(SidecarManager::new()))
        .setup(|app| {
            let state = app.state::<Mutex<SidecarManager>>();
            if let Ok(mut manager) = state.lock() {
                match app.path().app_data_dir() {
                    Ok(data_dir) => manager.set_data_dir(data_dir),
                    Err(error) => {
                        eprintln!("[sidecar] répertoire de données indisponible: {error}")
                    }
                }
                if let Err(error) = manager.ensure_running() {
                    eprintln!("[sidecar] démarrage impossible: {error}");
                }
            }
            start_supervisor(app.handle().clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_status,
            sidecar_health,
            sidecar_ping,
            sidecar_restart,
            sidecar_shutdown,
            project_list,
            project_create,
            project_data,
            project_brief_save,
            project_scenario_save,
            project_simulate,
            agent_call,
            agent_turn,
            sandbox_call,
            provider_call,
            provider_key_set,
            provider_key_status,
            provider_key_delete,
            provider_profile_save,
            provider_profile_delete,
            provider_test,
            provider_models,
            provider_chat
        ])
        .build(tauri::generate_context!())
        .expect("erreur au démarrage de l'application Tauri")
        .run(|app_handle, event| {
            if matches!(
                event,
                tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
            ) {
                SHUTTING_DOWN.store(true, Ordering::SeqCst);
                let state = app_handle.state::<Mutex<SidecarManager>>();
                let locked = state.lock();
                if let Ok(mut manager) = locked {
                    manager.shutdown();
                }
            }
        });
}
