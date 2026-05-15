const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        fontFamily: "system-ui, sans-serif",
        gap: "1rem",
      }}
    >
      <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0 }}>
        revenue-recovery-kit — dashboard scaffold
      </h1>
      <p style={{ color: "#6b7280", margin: 0 }}>
        Full AR dashboard lands on Day 5. Backend is live — check the health
        endpoint below.
      </p>
      <a
        href={`${apiUrl}/health`}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: "#2563eb", textDecoration: "underline" }}
      >
        {apiUrl}/health
      </a>
    </main>
  )
}
