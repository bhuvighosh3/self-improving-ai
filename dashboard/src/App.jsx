import React, { useEffect, useState } from "react";

function App() {
  const [health, setHealth] = useState(null);
  const [clients, setClients] = useState([]);
  const [requests, setRequests] = useState([]);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "error" }));

    fetch("/api/clients")
      .then((r) => r.json())
      .then(setClients)
      .catch(() => {});

    fetch("/api/requests")
      .then((r) => r.json())
      .then(setRequests)
      .catch(() => {});
  }, []);

  return (
    <>
      <header>
        <h1>Self-Improving AI Dashboard</h1>
        {health && (
          <span className={`status-badge ${health.status === "ok" ? "ok" : "error"}`}>
            {health.status === "ok" ? "Connected" : "Disconnected"}
            {health.model && ` — ${health.model}`}
          </span>
        )}
      </header>

      <div className="container">
        <div className="grid">
          <div className="card">
            <h2>Client Households</h2>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Risk</th>
                  <th>Goals</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c) => (
                  <tr key={c.client_id}>
                    <td>{c.client_id}</td>
                    <td>{c.profile?.name}</td>
                    <td>{c.profile?.risk_tolerance}</td>
                    <td>{c.profile?.goals?.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Advisor Requests</h2>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Intent</th>
                  <th>Client</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.intent}</td>
                    <td>{r.client_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card" style={{ marginTop: "1rem" }}>
          <h2>Request Log</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Request</th>
                <th>Expected Agents</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.request_text}</td>
                  <td>{r.expected_agents?.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

export default App;
