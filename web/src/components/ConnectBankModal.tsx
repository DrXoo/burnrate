import { useEffect, useState, type CSSProperties, type FormEvent } from "react";

import { getAspsps, startBankAuthorization } from "../lib/api";
import type { Aspsp } from "../types";

export interface ReconnectPrefill {
  country: string;
  aspspName: string;
  psuType: "personal" | "business";
}

interface ConnectBankModalProps {
  apiBase: string;
  onClose: () => void;
  prefill?: ReconnectPrefill | null;
}

const labelStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  fontSize: 12.5,
  fontWeight: 600,
  color: "var(--text-2)",
};

const primaryButton: CSSProperties = {
  border: "none",
  background: "var(--accent)",
  color: "#0a0d10",
  borderRadius: 9,
  padding: "9px 16px",
  font: "600 13px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

const secondaryButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "var(--bg-3)",
  color: "var(--text)",
  borderRadius: 9,
  padding: "9px 16px",
  font: "500 13px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

export function ConnectBankModal({ apiBase, onClose, prefill }: ConnectBankModalProps) {
  const [country, setCountry] = useState(prefill?.country ?? "ES");
  const [aspsps, setAspsps] = useState<Aspsp[]>([]);
  const [selectedBank, setSelectedBank] = useState("");
  const [psuType, setPsuType] = useState<"personal" | "business">(prefill?.psuType ?? "personal");
  const [loadingBanks, setLoadingBanks] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedCountry = country.trim().toUpperCase();

  // Reconnect: auto-load the bank list for the existing connection and preselect it,
  // so the user only has to confirm and re-authorize.
  useEffect(() => {
    if (!prefill) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        setLoadingBanks(true);
        setError(null);
        const banks = await getAspsps(apiBase, prefill.country.trim().toUpperCase());
        if (cancelled) {
          return;
        }
        setAspsps(banks);
        if (banks.some((bank) => bank.name === prefill.aspspName)) {
          setSelectedBank(prefill.aspspName);
        } else if (banks.length === 0) {
          setError(`No banks available for ${prefill.country.trim().toUpperCase()}.`);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : String(nextError));
        }
      } finally {
        if (!cancelled) {
          setLoadingBanks(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [prefill, apiBase]);

  async function handleFindBanks(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (normalizedCountry.length !== 2) {
      setError("Enter a 2-letter country code (e.g. ES).");
      return;
    }
    try {
      setLoadingBanks(true);
      setError(null);
      setSelectedBank("");
      const banks = await getAspsps(apiBase, normalizedCountry);
      setAspsps(banks);
      if (banks.length === 0) {
        setError(`No banks available for ${normalizedCountry}.`);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setLoadingBanks(false);
    }
  }

  async function handleContinue() {
    if (!selectedBank) {
      return;
    }
    try {
      setRedirecting(true);
      setError(null);
      const result = await startBankAuthorization(apiBase, {
        aspsp_name: selectedBank,
        aspsp_country: normalizedCountry,
        psu_type: psuType,
      });
      window.location.href = result.url;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setRedirecting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        background: "rgba(4, 6, 9, 0.55)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 420,
          background: "var(--bg-2)",
          border: "1px solid var(--line-2)",
          borderRadius: 16,
          padding: 24,
          boxShadow: "0 20px 60px rgba(0,0,0,.45)",
          animation: "br-rise .25s ease both",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>{prefill ? `Reconnect ${prefill.aspspName}` : "Connect a bank"}</div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              border: "none",
              background: "transparent",
              color: "var(--text-3)",
              fontSize: 20,
              lineHeight: 1,
              cursor: "pointer",
            }}
          >
            ×
          </button>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.55, margin: "0 0 16px" }}>
          {prefill
            ? "Re-authorize read-only access to resume syncing. You'll be sent to the bank and returned here."
            : "Choose your country and bank. You'll be sent to the bank to authorize read-only access, then returned here."}
        </p>

        <form onSubmit={handleFindBanks} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 14 }}>
          <label style={{ ...labelStyle, flex: 1 }}>
            Country code
            <input
              className="br-input"
              value={country}
              maxLength={2}
              onChange={(event) => setCountry(event.target.value)}
              placeholder="ES"
            />
          </label>
          <button type="submit" style={secondaryButton} disabled={loadingBanks || redirecting}>
            {loadingBanks ? "Loading…" : "Find banks"}
          </button>
        </form>

        {aspsps.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label style={labelStyle}>
              Bank
              <select
                className="br-sel"
                style={{ padding: "8px 26px 8px 10px" }}
                value={selectedBank}
                onChange={(event) => setSelectedBank(event.target.value)}
                disabled={redirecting}
              >
                <option value="">Choose a bank</option>
                {aspsps.map((bank) => (
                  <option key={`${bank.name}-${bank.country}`} value={bank.name}>
                    {bank.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              Account type
              <select
                className="br-sel"
                style={{ padding: "8px 26px 8px 10px" }}
                value={psuType}
                onChange={(event) => setPsuType(event.target.value as "personal" | "business")}
                disabled={redirecting}
              >
                <option value="personal">Personal</option>
                <option value="business">Business</option>
              </select>
            </label>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 4 }}>
              <button type="button" style={secondaryButton} onClick={onClose} disabled={redirecting}>
                Cancel
              </button>
              <button type="button" style={primaryButton} disabled={!selectedBank || redirecting} onClick={handleContinue}>
                {redirecting ? "Redirecting…" : "Continue to bank"}
              </button>
            </div>
          </div>
        ) : null}

        {error ? (
          <div
            style={{
              marginTop: 14,
              padding: "10px 12px",
              background: "var(--over-dim)",
              border: "1px solid color-mix(in oklab, var(--over) 30%, transparent)",
              borderRadius: 9,
              color: "var(--over)",
              fontSize: 12.5,
              lineHeight: 1.5,
            }}
          >
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}
