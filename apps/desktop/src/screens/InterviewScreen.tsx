import type {
  AgentPendingPermission,
  AgentSession,
  Project,
  RoleName,
} from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineAlert,
  TextareaField,
} from "@see/ui";
import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  project: Project;
  session: AgentSession | null;
  pending: AgentPendingPermission[];
  roles: RoleName[];
  busy: boolean;
  error: string;
  onSend: (message: string) => Promise<void>;
  onResume: (approval: { tool: string; callId: string; decision: "allow" | "deny" | "always" }) => Promise<void>;
  onOpenSettings: () => void;
}

const STATE_LABELS: Record<string, string> = {
  idea: "Idée",
  interviewing: "Entretien",
  brief_draft: "Brief en cours",
  brief_validated: "Brief validé",
  hypotheses_set: "Hypothèses prêtes",
  simulating: "Simulation",
  results_ready: "Résultats prêts",
  narrating: "Narration",
  done: "Terminé",
};

const ROLE_LABELS: Record<RoleName, string> = {
  interviewer: "Intervieweur",
  modeler: "Modélisateur",
  narrator: "Narrateur",
  delegate: "Délégué",
  coder: "Codeur",
};

const SUGGESTIONS = [
  "Je veux ouvrir un dépôt de boissons à Abidjan avec 500 000 FCFA.",
  "Mon idée : vendre des repas préparés près des bureaux.",
  "Je veux tester un petit élevage de poulets de chair.",
];

export function InterviewScreen({
  project,
  session,
  pending,
  roles,
  busy,
  error,
  onSend,
  onResume,
  onOpenSettings,
}: Props) {
  const [draft, setDraft] = useState("");
  const [queued, setQueued] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const messages = useMemo(
    () =>
      (session?.thread ?? []).filter(
        (message) =>
          (message.role === "user" || message.role === "assistant") && message.content.trim(),
      ),
    [session],
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, queued, pending.length]);

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setQueued(text);
    try {
      await onSend(text);
    } finally {
      setQueued(null);
    }
  };

  const hasRole = roles.includes(session?.role ?? "interviewer");

  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Entretien guidé</p>
          <h1>{project.name}</h1>
          <p className="ui-muted">
            Décrivez votre idée. L'agent pose les questions manquantes et prépare le brief.
          </p>
        </div>
        <div className="ui-actions">
          <Badge tone="accent">{STATE_LABELS[session?.state ?? "idea"] ?? session?.state}</Badge>
          <Badge>{ROLE_LABELS[session?.role ?? "interviewer"]}</Badge>
        </div>
      </div>

      {!hasRole ? (
        <InlineAlert tone="warn" title="Aucun fournisseur associé">
          Configurez un profil et assignez-le au rôle d'intervieweur dans les réglages.{" "}
          <Button variant="ghost" size="small" onClick={onOpenSettings}>
            Ouvrir les réglages
          </Button>
        </InlineAlert>
      ) : null}

      {error ? <InlineAlert tone="danger" title="Action impossible">{error}</InlineAlert> : null}

      <Card className="chat-card">
        <CardHeader
          eyebrow="Conversation"
          title="Votre entretien"
          description="Les réponses restent stockées dans ce projet, sur cet appareil."
        />
        <div className="chat-thread" role="log" aria-live="polite">
          {messages.length === 0 && !queued ? (
            <EmptyState
              title="Commencez par votre idée"
              description="Pas besoin d'un business plan. Une phrase suffit pour démarrer."
              action={
                <div className="suggestion-list">
                  {SUGGESTIONS.map((suggestion) => (
                    <Button
                      key={suggestion}
                      variant="secondary"
                      size="small"
                      onClick={() => setDraft(suggestion)}
                      disabled={busy}
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              }
            />
          ) : null}
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={message.role === "user" ? "chat-message chat-message--user" : "chat-message"}
            >
              <span className="chat-message__role">
                {message.role === "user" ? "Vous" : ROLE_LABELS[session?.role ?? "interviewer"]}
              </span>
              <p>{message.content}</p>
            </div>
          ))}
          {queued ? (
            <div className="chat-message chat-message--user">
              <span className="chat-message__role">Vous</span>
              <p>{queued}</p>
            </div>
          ) : null}
          {busy ? (
            <div className="chat-message chat-message--thinking">
              <span className="chat-message__role">Agent</span>
              <p>Il réfléchit, valide les outils et met à jour le brief…</p>
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>

        {pending.length > 0 ? (
          <div className="permission-stack">
            {pending.map((permission) => (
              <div className="permission-card" key={permission.callId}>
                <div>
                  <strong>Permission requise : {permission.tool}</strong>
                  <p>{permission.reason}</p>
                  <span className="ui-muted">Appel {permission.callId}</span>
                </div>
                <div className="ui-actions">
                  <Button
                    size="small"
                    onClick={() =>
                      void onResume({ tool: permission.tool, callId: permission.callId, decision: "allow" })
                    }
                    disabled={busy}
                  >
                    Autoriser
                  </Button>
                  <Button
                    size="small"
                    variant="secondary"
                    onClick={() =>
                      void onResume({ tool: permission.tool, callId: permission.callId, decision: "always" })
                    }
                    disabled={busy}
                  >
                    Toujours autoriser
                  </Button>
                  <Button
                    size="small"
                    variant="danger"
                    onClick={() =>
                      void onResume({ tool: permission.tool, callId: permission.callId, decision: "deny" })
                    }
                    disabled={busy}
                  >
                    Refuser
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        <div className="composer">
          <TextareaField
            label="Votre message"
            value={draft}
            onChange={setDraft}
            rows={3}
            placeholder="Décrivez votre idée, vos clients, vos contraintes…"
            hint="L'agent répond et met à jour le brief après validation des outils."
          />
          <Button onClick={send} disabled={busy || !draft.trim() || pending.length > 0}>
            Envoyer
          </Button>
        </div>
        <p className="ui-muted">
          L'agent ne calcule aucun chiffre : il prépare le brief et appelle le moteur quand vous le
          validez.
        </p>
      </Card>
    </div>
  );
}
