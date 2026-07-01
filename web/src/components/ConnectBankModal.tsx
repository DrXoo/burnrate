import { useState, type FormEvent } from "react";

import { getAspsps, startBankAuthorization } from "../lib/api";
import type { Aspsp } from "../types";
import { Modal } from "./ui/Modal";

interface ConnectBankModalProps {
  apiBase: string;
  onClose: () => void;
}

export function ConnectBankModal({ apiBase, onClose }: ConnectBankModalProps) {
  const [country, setCountry] = useState("ES");
  const [aspsps, setAspsps] = useState<Aspsp[]>([]);
  const [selectedBank, setSelectedBank] = useState("");
  const [psuType, setPsuType] = useState<"personal" | "business">("personal");
  const [loadingBanks, setLoadingBanks] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedCountry = country.trim().toUpperCase();

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
      // Hand the browser off to the bank's authorization page.
      window.location.href = result.url;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setRedirecting(false);
    }
  }

  return (
    <Modal title="Connect a bank" onClose={onClose}>
      <div className="stack">
        <p className="meta-copy">
          Choose your country and bank. You will be sent to the bank to authorize access, then returned here.
        </p>

        <form className="mini-form" onSubmit={handleFindBanks}>
          <label>
            Country code
            <input
              value={country}
              maxLength={2}
              onChange={(event) => setCountry(event.target.value)}
              placeholder="ES"
            />
          </label>
          <button type="submit" className="button button-secondary" disabled={loadingBanks || redirecting}>
            {loadingBanks ? "Loading banks..." : "Find banks"}
          </button>
        </form>

        {aspsps.length > 0 ? (
          <>
            <label>
              Bank
              <select
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
            <label>
              Account type
              <select
                value={psuType}
                onChange={(event) => setPsuType(event.target.value as "personal" | "business")}
                disabled={redirecting}
              >
                <option value="personal">Personal</option>
                <option value="business">Business</option>
              </select>
            </label>
            <div className="inline-actions">
              <button type="button" className="button" disabled={!selectedBank || redirecting} onClick={handleContinue}>
                {redirecting ? "Redirecting..." : "Continue to bank"}
              </button>
              <button type="button" className="button button-secondary" onClick={onClose} disabled={redirecting}>
                Cancel
              </button>
            </div>
          </>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}
      </div>
    </Modal>
  );
}
