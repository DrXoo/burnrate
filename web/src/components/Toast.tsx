interface ToastProps {
  message: string;
  tone?: "good" | "over";
}

export function Toast({ message, tone = "good" }: ToastProps) {
  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        background: "var(--bg-4)",
        color: "var(--text)",
        border: "1px solid var(--line-2)",
        borderRadius: 11,
        padding: "11px 18px",
        fontSize: 13,
        fontWeight: 500,
        boxShadow: "0 10px 30px rgba(0,0,0,.35)",
        display: "flex",
        alignItems: "center",
        gap: 9,
        animation: "br-rise .25s ease both",
        maxWidth: "min(90vw, 460px)",
      }}
    >
      <span
        style={{
          flex: "none",
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: tone === "over" ? "var(--over)" : "var(--good)",
        }}
      />
      {message}
    </div>
  );
}
