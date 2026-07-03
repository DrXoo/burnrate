import { IconCard, LogoMark } from "./icons";

interface FirstRunProps {
  onConnect: () => void;
}

const reasons = [
  {
    title: "Link read-only",
    body: "We never move money. Access is view-only and revocable any time.",
  },
  {
    title: "Self-hosted, single owner",
    body: "Your data stays on your server. No accounts, no upsells.",
  },
  {
    title: "Auto-sync, low effort",
    body: "Transactions land on their own. You just triage the unknowns.",
  },
];

export function FirstRun({ onConnect }: FirstRunProps) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 40,
        background:
          "radial-gradient(120% 90% at 50% -10%, color-mix(in oklab, var(--accent) 12%, var(--bg)) 0%, var(--bg) 60%)",
      }}
    >
      <div style={{ maxWidth: 520, width: "100%", textAlign: "center", animation: "br-rise .5s ease both" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 9, marginBottom: 34 }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 7,
              background: "var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <LogoMark />
          </div>
          <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.02em" }}>BurnRate</span>
        </div>

        <div
          style={{
            width: 96,
            height: 96,
            borderRadius: 24,
            margin: "0 auto 26px",
            background: "var(--bg-2)",
            border: "1px solid var(--line)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "var(--card-shadow)",
          }}
        >
          <IconCard color="var(--accent)" />
        </div>

        <h1 className="num" style={{ fontSize: 29, fontWeight: 600, margin: "0 0 12px", letterSpacing: "-0.02em" }}>
          Connect a bank to see your burn rate
        </h1>
        <p
          style={{
            fontSize: 15.5,
            lineHeight: 1.6,
            color: "var(--text-2)",
            margin: "0 auto 30px",
            maxWidth: 400,
          }}
        >
          BurnRate reads your transactions over open banking (PSD2) and turns them into one honest answer: how much you
          have left, and how fast it's going.
        </p>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            textAlign: "left",
            maxWidth: 400,
            margin: "0 auto 30px",
          }}
        >
          {reasons.map((reason, index) => (
            <div
              key={reason.title}
              style={{
                display: "flex",
                gap: 12,
                alignItems: "flex-start",
                padding: "14px 16px",
                background: "var(--bg-2)",
                border: "1px solid var(--line)",
                borderRadius: 12,
              }}
            >
              <div
                style={{
                  flex: "none",
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  background: "var(--good-dim)",
                  color: "var(--good)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                {index + 1}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>{reason.title}</div>
                <div style={{ fontSize: 12.5, color: "var(--text-2)", lineHeight: 1.5 }}>{reason.body}</div>
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={onConnect}
          style={{
            width: "100%",
            maxWidth: 400,
            padding: 14,
            border: "none",
            borderRadius: 12,
            background: "var(--accent)",
            color: "#0a0d10",
            font: "600 15px 'Hanken Grotesque', sans-serif",
            cursor: "pointer",
            boxShadow: "0 6px 22px color-mix(in oklab, var(--accent) 35%, transparent)",
          }}
        >
          Connect a bank
        </button>
        <div style={{ marginTop: 14, fontSize: 12, color: "var(--text-3)" }}>Powered by Enable Banking · PSD2</div>
      </div>
    </div>
  );
}
