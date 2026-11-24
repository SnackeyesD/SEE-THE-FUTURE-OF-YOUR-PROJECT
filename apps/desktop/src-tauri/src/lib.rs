mod keychain;
mod sidecar;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use serde_json::{json, Value};
use sidecar::{SidecarManager, SidecarStatus};
use tauri::Manager;

static SHUTTING_DOWN: AtomicBool = AtomicBool::new(false);

fn start_supervisor(handle: tauri::AppHandle) {
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(2));
        if SHUTTING_DOWN.load(Ordering::SeqCst) {
            break;
        }

        let state = handle.state::<Mutex<SidecarManager>>();
        let locked = state.lock();
        if let Ok(manager) = locked {
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    Ok(handle.status())
}

#[tauri::command]
fn sidecar_health(state: tauri::State<'_, Mutex<SidecarManager>>) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("health", json!({}))
}

#[tauri::command]
fn sidecar_ping(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    echo: Option<String>,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    let params = match echo {
        Some(echo) => json!({ "echo": echo }),
        None => json!({}),
    };
    handle.request("ping", params)
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

const BENCHMARK_METHODS: &[&str] = &[
    "benchmark.lookup",
    "benchmark.pack.list",
    "benchmark.pack.import",
];

#[tauri::command]
fn project_list(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    include_archived: Option<bool>,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(
        "project.create",
        json!({
            "name": name,
            "description": description.unwrap_or_default(),
            "currency": currency.unwrap_or_else(|| "XOF".into()),
        }),
    )
}

#[tauri::command]
fn project_create_from_template(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    template_id: String,
    name: Option<String>,
    currency: Option<String>,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    let mut params = json!({ "templateId": template_id });
    if let Some(name) = name {
        params["name"] = json!(name);
    }
    if let Some(currency) = currency {
        params["currency"] = json!(currency);
    }
    handle.request("project.createFromTemplate", params)
}

#[tauri::command]
fn template_list(
    state: tauri::State<'_, Mutex<SidecarManager>>,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("template.list", json!({}))
}

#[tauri::command]
fn report_build(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("report.build", params)
}

#[tauri::command]
fn report_build_pdf(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("report.buildPdf", params)
}

#[tauri::command]
fn project_data(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("project.data", params)
}

#[tauri::command]
fn project_brief_save(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("project.brief.save", params)
}

#[tauri::command]
fn project_scenario_save(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("project.scenario.save", params)
}

#[tauri::command]
fn project_scenario_branch(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("project.scenario.branch", params)
}

#[tauri::command]
fn project_simulate(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("project.simulate", params)
}

const PROJECT_CALL_METHODS: &[&str] = &[
    "project.scenario.list",
    "project.scenario.get",
    "project.scenario.rename",
    "project.scenario.archive",
    "project.scenario.unarchive",
    "project.run.list",
    "project.run.pin",
    "project.run.compare",
    "project.version.create",
    "project.version.list",
    "project.version.restore",
    "project.version.delete",
];

/// Passerelle explicite pour les méthodes de gestion de branches et versions.
/// Seules les méthodes listées sont joignables : le shell n'expose pas le
/// dispatcher JSON-RPC complet à l'interface.
#[tauri::command]
fn project_call(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    if !PROJECT_CALL_METHODS.contains(&method.as_str()) {
        return Err(format!("méthode projet non autorisée: {method}"));
    }
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(&method, params)
}

#[tauri::command]
fn simulation_start(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.start", params)
}

#[tauri::command]
fn simulation_cancel(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    run_id: Option<String>,
    job_id: Option<String>,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    let mut params = json!({});
    if let Some(run_id) = run_id {
        params["runId"] = Value::String(run_id);
    }
    if let Some(job_id) = job_id {
        params["jobId"] = Value::String(job_id);
    }
    handle.request("simulation.cancel", params)
}

#[tauri::command]
fn simulation_surface(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.surface", params)
}

#[tauri::command]
fn simulation_goalseek(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.goalseek", params)
}

#[tauri::command]
fn simulation_trajectories(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.trajectories", params)
}

#[tauri::command]
fn simulation_run_params(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.run_params", params)
}

#[tauri::command]
fn simulation_provenance(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.provenance", params)
}

#[tauri::command]
fn simulation_explain(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let params = inject_api_key(params)?;
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("simulation.explain", params)
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(&method, params)
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(&method, params)
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

    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    let prepared = handle.request("agent.prepare", prepare)?;
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
    handle.request("agent.turn", params)
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(&method, params)
}

#[tauri::command]
fn benchmark_call(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    if !BENCHMARK_METHODS.contains(&method.as_str()) {
        return Err(format!("méthode benchmark non autorisée: {method}"));
    }
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request(&method, params)
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("provider.profile.save", params)
}

#[tauri::command]
fn provider_profile_delete(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    project_id: String,
    profile_id: String,
) -> Result<Value, String> {
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    let listing = handle.request("provider.profile.list", json!({ "projectId": project_id }))?;
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
    handle.request(
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
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("provider.test", params)
}

#[tauri::command]
fn provider_models(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let params = inject_api_key(params)?;
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("provider.models", params)
}

#[tauri::command]
fn provider_chat(
    state: tauri::State<'_, Mutex<SidecarManager>>,
    params: Value,
) -> Result<Value, String> {
    let params = inject_api_key(params)?;
    let handle = state.lock().map_err(|error| error.to_string())?.handle();
    handle.request("provider.chat", params)
}

#[tauri::command]
fn sidecar_restart(
    state: tauri::State<'_, Mutex<SidecarManager>>,
) -> Result<SidecarStatus, String> {
    let manager = state.lock().map_err(|error| error.to_string())?;
    Ok(manager.restart())
}

#[tauri::command]
fn sidecar_shutdown(state: tauri::State<'_, Mutex<SidecarManager>>) -> Result<(), String> {
    let manager = state.lock().map_err(|error| error.to_string())?;
    manager.shutdown();
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .manage(Mutex::new(SidecarManager::new()))
        .setup(|app| {
            let state = app.state::<Mutex<SidecarManager>>();
            if let Ok(manager) = state.lock() {
                manager.attach_app(app.handle().clone());
                match app.path().app_data_dir() {
                    Ok(data_dir) => manager.set_data_dir(data_dir),
                    Err(error) => {
                        eprintln!("[sidecar] rǸpertoire de donnǸes indisponible: {error}")
                    }
                }
                if let Ok(resource_dir) = app.path().resource_dir() {
                    let benchmark_dir = resource_dir.join("benchmark-packs");
                    if benchmark_dir.is_dir() {
                        manager.set_benchmark_dir(benchmark_dir);
                    }
                    let examples_dir = resource_dir.join("examples");
                    if examples_dir.is_dir() {
                        manager.set_examples_dir(examples_dir);
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
            project_create_from_template,
            template_list,
            report_build,
            report_build_pdf,
            project_data,
            project_brief_save,
            project_scenario_save,
            project_scenario_branch,
            project_simulate,
            project_call,
            simulation_start,
            simulation_cancel,
            simulation_surface,
            simulation_goalseek,
            simulation_trajectories,
            simulation_run_params,
            simulation_provenance,
            simulation_explain,
            agent_call,
            agent_turn,
            sandbox_call,
            benchmark_call,
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
                if let Ok(manager) = locked {
                    manager.shutdown();
                }
            }
        });
}
