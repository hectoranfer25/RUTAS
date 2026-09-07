import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const truckIcon = L.divIcon({
  className: "truck-marker",  
  html: "🚚",
  iconSize: [35, 35],
  iconAnchor: [18, 18],
});

const loadIcon = L.divIcon({
  className: "location-marker load",  
  html: `<div class="dump-icon">⛏️</div>`,
  iconSize: [25, 25],
  iconAnchor: [15, 15],
});

const dumpIcon = L.divIcon({
  className: "location-marker dump",
  html: `<div class="dump-icon">🏗️</div>`,
  iconSize: [25, 25],
  iconAnchor: [15, 15],
});

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) map.fitBounds(points, { padding: [24, 24] });
  }, [map, points]);
  return null;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body?.detail?.message || body?.detail || "Error de API");
  return body;
}

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [locations, setLocations] = useState({ load: [], dump: [] });
  const [simulation, setSimulation] = useState({ status: "idle", trucks: [] });
  const [report, setReport] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const [r, l] = await Promise.all([api("/routes"), api("/locations")]);
      setRoutes(r.routes || []);
      setLocations(l);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const poll = async () => {
    try {
      const [current, rep] = await Promise.all([
        api("/simulations/current"),
        api("/simulations/report"),
      ]);
      setSimulation(current);
      setReport(rep.report || []);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  const start = async () => {
    try {
      setError("");
      await api("/simulations/start", { method: "POST" });
      await poll();
    } catch (e) {
      setError(e.message);
    }
  };

  const reset = async () => {
    try {
      await api("/simulations/reset", { method: "POST" });
      await poll();
    } catch (e) {
      setError(e.message);
    }
  };

  const allPoints = useMemo(
    () => routes.flatMap(r => r.points.map(p => [p[0], p[1]])),
    [routes]
  );
  const center = allPoints[0] || [-6.48, -78.50];

  return (
    <main className="app">
      <header className="topbar">
        <div>          
          <h1>SIMULADOR DE RUTAS - CAMIONES  </h1>          
        </div>
        <div className="actions">
          <button onClick={start}>▶ Iniciar / reiniciar</button>
          <button className="secondary" onClick={reset}>■ Detener</button>
        </div>
      </header>

      {loading && <div className="banner">Cargando datos…</div>}
      {error && <div className="banner error">Error: {error}</div>}

      <section className="layout">
        <div className="map-card">
          <MapContainer center={center} zoom={13} className="map">
            <TileLayer
              attribution='&copy; OpenStreetMap contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitBounds points={allPoints} />
            {routes.map(route => (
              <Polyline key={route.id_trm_cs} positions={route.points} pathOptions={{ color: route.color, weight: 5 }}>
                <Popup>{route.nombre_tramo || `Tramo ${route.id_trm_cs}`}</Popup>
              </Polyline>
            ))}
            {locations.load.map(x => (
              <Marker key={`l-${x.id}`} position={x.coor} icon={loadIcon}>
                <Popup><b>Carga</b><br />{x.name}</Popup>
              </Marker>
            ))}
            {locations.dump.map(x => (
              <Marker key={`d-${x.id}`} position={x.coor} icon={dumpIcon}>
                <Popup><b>Descarga</b><br />{x.name}</Popup>
              </Marker>
            ))}
            {simulation.trucks?.map(t => (
              <Marker key={t.id} position={[t.lat, t.lon]} icon={truckIcon}>
                <Popup>
                  <b>{t.id}</b><br />
                  {t.speed_kmh.toFixed(1)} km/h · {t.status}<br />
                  {t.load_name} → {t.dump_name}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
          <div className="legend">
            <span><i className="legend-load">⛏️</i> CARGA</span>
            <span><i className="legend-dump">🏗️</i> DESCARGA</span>
            <span>🚚 CAMION</span>
          </div>
        </div>

        <aside className="side">
          <div className="panel">
            <h2>Estado actual</h2>
            <div className="status">
              <span className={`dot ${simulation.status === "running" ? "ok" : ""}`}></span>
              {simulation.status === "running" ? "Simulación activa" : "Sin simulación"}
            </div>
            {simulation.simulation_id && (
              <small>Seed: {simulation.seed} · ID: {simulation.simulation_id.slice(0, 8)}</small>
            )}
          </div>

          <div className="panel">
            <h2>Camiones</h2>
            <div className="truck-list">
              {(simulation.trucks || []).map(t => (
                <div className="truck-row" key={t.id}>
                  <div>
                    <b>{t.id}</b>
                    <small>{t.load_name} → {t.dump_name}</small>
                  </div>
                  <div className="speed">{t.speed_kmh.toFixed(1)} <small>km/h</small></div>
                  <div className="progress"><span style={{ width: `${t.progress * 100}%` }} /></div>
                  <small>{t.status} · {Math.round(t.progress * 100)}%</small>
                </div>
              ))}
              {!simulation.trucks?.length && <div className="muted">Inicia la simulación para ver los cinco camiones.</div>}
            </div>
          </div>
        </aside>
      </section>

      <section className="panel report">
        <div className="report-head">
          <div>
            <h2>Reporte de velocidad</h2>
            <p>Media aritmética de las muestras; fuera de rango significa &lt; 25 o &gt; 50 km/h.</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Camión</th><th>Muestras</th><th>Mín.</th><th>Máx.</th><th>Promedio</th><th>Fuera 25–50</th><th>Explicación</th>
              </tr>
            </thead>
            <tbody>
              {report.map(r => (
                <tr key={r.truck_id}>
                  <td><b>{r.truck_id}</b></td>
                  <td>{r.samples}</td>
                  <td>{r.min_speed_kmh}</td>
                  <td>{r.max_speed_kmh}</td>
                  <td><b>{r.avg_speed_kmh}</b></td>
                  <td>{r.outside_25_50_samples} ({r.outside_25_50_percent}%)</td>
                  <td>{r.explanation}</td>
                </tr>
              ))}
              {!report.length && (
                <tr><td colSpan="7" className="muted">No hay reporte todavía.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <footer>
        <span>@HectorLopez</span>
        <span>2026</span>
      </footer>
    </main>
  );
}
