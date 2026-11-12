import type { BenchmarkPackInfo, BenchmarkPackListResult } from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  InlineAlert,
  Table,
} from "@see/ui";
import { useCallback, useEffect, useState } from "react";
import { importBenchmarkPack, listBenchmarkPacks } from "../lib/ipc";
import { formatDateTime } from "../lib/format";
import type { LogLevel } from "../lib/logs";

interface Props {
  disabled: boolean;
  onLog: (level: LogLevel, message: string) => void;
}

function statusTone(status: BenchmarkPackInfo["status"]) {
  if (status === "verified") return "ok" as const;
  if (status === "unverified") return "warn" as const;
  return "danger" as const;
}

export function BenchmarkPacksPanel({ disabled, onLog }: Props) {
  const [result, setResult] = useState<BenchmarkPackListResult | null>(null);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setResult(await listBenchmarkPacks());
      setError("");
    } catch (reason) {
      setError(String(reason));
      onLog("error", `Packs de références: ${String(reason)}`);
    }
  }, [onLog]);

  useEffect(() => {
    if (!disabled) void load();
  }, [disabled, load]);

  const importPack = async () => {
    if (!path.trim()) {
      setError("Chemin du pack requis.");
      return;
    }
    setBusy(true);
    try {
      const imported = await importBenchmarkPack(path.trim());
      setPath("");
      setError("");
      await load();
      onLog(
        "success",
        `Pack ${imported.pack.name} ${imported.pack.version} importé (${imported.pack.status}).`,
      );
    } catch (reason) {
      setError(String(reason));
      onLog("error", `Import du pack: ${String(reason)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader
        eyebrow="Références de marché"
        title="Packs de benchmarks signés"
        description="Les valeurs sont sourcées, datées et vérifiées par clé Ed25519 avant usage."
        action={
          <Button variant="ghost" size="small" onClick={() => void load()} disabled={disabled}>
            Recharger
          </Button>
        }
      />
      {error ? (
        <InlineAlert tone="danger" title="Packs indisponibles">
          {error}
        </InlineAlert>
      ) : null}
      <Table
        columns={[
          {
            key: "name",
            header: "Pack",
            render: (pack) => (
              <div>
                <strong>{pack.name}</strong>
                <p className="ui-muted">{pack.packId}</p>
              </div>
            ),
          },
          { key: "version", header: "Version", mono: true },
          {
            key: "zone",
            header: "Zone",
            render: (pack) => `${pack.country}${pack.region ? ` — ${pack.region}` : ""}`,
          },
          { key: "valueCount", header: "Valeurs", mono: true },
          {
            key: "publishedAt",
            header: "Publié",
            mono: true,
            render: (pack) => formatDateTime(pack.publishedAt),
          },
          {
            key: "status",
            header: "Statut",
            render: (pack) => <Badge tone={statusTone(pack.status)}>{pack.status}</Badge>,
          },
          {
            key: "source",
            header: "Origine",
            render: (pack) => (
              <div>
                <span>{pack.source}</span>
                <p className="ui-muted">{pack.keyId || "clé inconnue"}</p>
              </div>
            ),
          },
        ]}
        rows={result?.packs ?? []}
        rowKey={(pack) => `${pack.packId}@${pack.version}`}
        empty="Aucun pack installé."
      />
      {result && result.errors.length > 0 ? (
        <InlineAlert tone="warn" title="Packs ignorés">
          {result.errors.join(" · ")}
        </InlineAlert>
      ) : null}
      <div className="ui-field-grid">
        <Field
          label="Fichier .json à importer"
          value={path}
          placeholder="C:\chemin\pack.json"
          onChange={(event) => setPath(event.target.value)}
        />
      </div>
      <div className="ui-actions ui-actions--end">
        <Button
          variant="secondary"
          onClick={() => void importPack()}
          disabled={disabled || busy}
        >
          Importer le pack et sa signature
        </Button>
      </div>
    </Card>
  );
}
