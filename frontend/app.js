/**
 * ============================================
 *  Barracas Pro v2 - Logica del Frontend
 *  SPA sin frameworks, todo vanilla JS
 * ============================================
 */

const API = "";  // Mismo origen (Railway sirve frontend y backend juntos)

// =============================================
//  ESTADO GLOBAL
// =============================================
let currentUser = null;
let authToken = null;
let allBarracas = [];
let allVendedores = [];
let map, markersLayer;

// =============================================
//  AUTENTICACION
// =============================================

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById("login-user").value;
    const password = document.getElementById("login-pass").value;

    try {
        const res = await fetch(`${API}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        if (!res.ok) {
            document.getElementById("login-error").textContent = "Usuario o contrasena incorrectos";
            return;
        }

        const data = await res.json();
        authToken = data.access_token;
        currentUser = data;

        localStorage.setItem("bp_token", authToken);
        localStorage.setItem("bp_user", JSON.stringify(currentUser));

        enterApp();
    } catch (err) {
        document.getElementById("login-error").textContent = "Error de conexion con el servidor";
    }
}

function handleLogout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem("bp_token");
    localStorage.removeItem("bp_user");
    document.getElementById("view-app").classList.remove("active");
    document.getElementById("view-login").classList.add("active");
}

function enterApp() {
    document.getElementById("view-login").classList.remove("active");
    document.getElementById("view-app").classList.add("active");
    document.getElementById("user-info").textContent = `${currentUser.nombre_completo} (${currentUser.rol})`;

    if (currentUser.rol === "admin") {
        document.body.classList.add("is-admin");
    }

    // Cargar datos iniciales
    loadBarracas();
    loadVendedores();
}

function authHeaders() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
    };
}

function apiGet(url) {
    return fetch(url, { headers: authHeaders() }).then(r => r.json());
}

function apiPost(url, body) {
    return fetch(url, { method: "POST", headers: authHeaders(), body: JSON.stringify(body) }).then(r => r.json());
}

function apiPatch(url, body) {
    return fetch(url, { method: "PATCH", headers: authHeaders(), body: JSON.stringify(body) }).then(r => r.json());
}

function apiDelete(url) {
    return fetch(url, { method: "DELETE", headers: authHeaders() });
}

// =============================================
//  NAVEGACION (Tabs)
// =============================================

function switchTab(name, btn) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(s => s.classList.remove("active"));
    if (btn) btn.classList.add("active");
    const el = document.getElementById(`tab-${name}`);
    if (el) el.classList.add("active");

    // Inicializar componentes segun tab
    if (name === "mapa" && !map) setTimeout(initMap, 100);
    if (name === "calendario" && !window.calendarioIniciado) initCalendario();
    if (name === "reportes") loadReportes();
    if (name === "admin") loadAdminData();
}

// =============================================
//  MAPA (OpenLayers)
// =============================================

function initMap() {
    markersLayer = new ol.layer.Vector({
        source: new ol.source.Vector(),
        style: feature => {
            const sel = feature.get("selected");
            const visited = feature.get("visited");
            let color = "#4caf50";
            if (visited) color = "#f44336";
            else if (sel) color = "#2196F3";
            return new ol.style.Style({
                image: new ol.style.Circle({ radius: 9, fill: new ol.style.Fill({ color }), stroke: new ol.style.Stroke({ color: "#fff", width: 2 }) }),
                text: new ol.style.Text({ text: feature.get("name").substring(0, 18), font: "11px sans-serif", offsetY: -15, fill: new ol.style.Fill({ color: "#333" }), stroke: new ol.style.Stroke({ color: "#fff", width: 3 }) })
            });
        }
    });

    map = new ol.Map({
        target: "map",
        layers: [new ol.layer.Tile({ source: new ol.source.OSM() }), markersLayer],
        view: new ol.View({ center: ol.proj.fromLonLat([-56.1645, -34.9011]), zoom: 12 })
    });

    map.on("click", evt => {
        const feature = map.forEachFeatureAtPixel(evt.pixel, f => f);
        if (feature && feature.get("barracaId")) showBarracaModal(feature.get("barracaId"));
    });

    renderMarkers();
}

async function loadBarracas() {
    try {
        allBarracas = await apiGet(`${API}/barracas`);
        renderBarrasList();
        renderMarkers();
    } catch (e) { console.error("Error cargando barracas:", e); }
}

function renderBarrasList() {
    const city = document.getElementById("filter-city").value.toLowerCase();
    const container = document.getElementById("barracas-list");
    container.innerHTML = "";

    const filtered = city ? allBarracas.filter(b => (b.ciudad || "").toLowerCase().includes(city)) : allBarracas;

    filtered.forEach(b => {
        const div = document.createElement("div");
        div.className = "barraca-item";
        div.textContent = `${b.nombre} - ${b.ciudad || "Sin ciudad"}`;
        div.onclick = () => {
            if (b.latitude && b.longitude) {
                map.getView().animate({ center: ol.proj.fromLonLat([b.longitude, b.latitude]), zoom: 15 });
            }
            showBarracaModal(b.id);
        };
        container.appendChild(div);
    });
}

function filterBarracas() { renderBarrasList(); }

function renderMarkers() {
    if (!markersLayer) return;
    const source = markersLayer.getSource();
    source.clear();

    allBarracas.forEach(b => {
        if (!b.latitude || !b.longitude) return;
        const f = new ol.Feature({
            geometry: new ol.geom.Point(ol.proj.fromLonLat([b.longitude, b.latitude])),
            barracaId: b.id, name: b.nombre, selected: false, visited: false
        });
        source.addFeature(f);
    });

    if (source.getFeatures().length > 0) {
        const ext = source.getExtent();
        map.getView().fit(ext, { padding: [40, 40, 40, 40], maxZoom: 13 });
    }
}

// =============================================
//  DETALLE DE BARRACA (Modal)
// =============================================

async function showBarracaModal(barracaId) {
    const barraca = allBarracas.find(b => b.id === barracaId);
    if (!barraca) return;

    let notas = [];
    try { notas = await apiGet(`${API}/barracas/${barracaId}/notas`); } catch (e) {}

    const body = document.getElementById("modal-body");
    body.innerHTML = `
        <h2>${barraca.nombre}</h2>
        <p><strong>Direccion:</strong> ${barraca.direccion || "No especificada"}</p>
        <p><strong>Ciudad:</strong> ${barraca.ciudad || "-"} | <strong>Depto:</strong> ${barraca.departamento || "-"}</p>
        <p><strong>Telefono:</strong> ${barraca.telefono || "-"}</p>
        <p><strong>Contacto:</strong> ${barraca.contacto || "-"}</p>
        ${barraca.notas_generales ? `<p><strong>Notas:</strong> ${barraca.notas_generales}</p>` : ""}

        <h3 style="margin-top:20px;">Notas recientes</h3>
        ${notas.length ? notas.map(n => `<div class="nota-item"><strong>${n.vendedor_nombre}</strong> <small>${n.created_at ? n.created_at.substring(0, 10) : ""}</small><br>${n.contenido}</div>`).join("") : "<p style=color:#888>No hay notas</p>"}

        <h3 style="margin-top:15px;">Agregar nota</h3>
        <textarea id="nueva-nota" rows="2" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;" placeholder="Escribir nota..."></textarea>
        <button onclick="agregarNota(${barracaId})" class="btn-primary" style="margin-top:8px;">Guardar nota</button>

        <h3 style="margin-top:15px;">Acciones</h3>
        <button onclick="planificarVisita(${barracaId})" class="btn-primary">📅 Planificar Visita</button>
        <button onclick="marcarVisitada(${barracaId})" style="margin-left:8px;padding:8px 16px;background:#4caf50;color:white;border:none;border-radius:6px;cursor:pointer;">✅ Marcar Visitada</button>
    `;
    document.getElementById("modal-barraca").style.display = "flex";
}

function closeModal() {
    document.getElementById("modal-barraca").style.display = "none";
}

async function agregarNota(barracaId) {
    const contenido = document.getElementById("nueva-nota").value.trim();
    if (!contenido) return;
    try {
        await apiPost(`${API}/barracas/${barracaId}/notas`, { barraca_id: barracaId, contenido });
        document.getElementById("nueva-nota").value = "";
        showBarracaModal(barracaId);
    } catch (e) { alert("Error guardando nota"); }
}

// =============================================
//  VISITAS
// =============================================

function showVisitaForm() {
    const sel = document.getElementById("vf-barraca");
    sel.innerHTML = allBarracas.map(b => `<option value="${b.id}">${b.nombre}</option>`).join("");
    document.getElementById("visita-form").style.display = "block";
}

async function loadVendedores() {
    try {
        if (currentUser.rol === "admin") {
            allVendedores = await apiGet(`${API}/admin/usuarios`);
        }
    } catch (e) {}
}

async function crearVisita() {
    const barracaId = parseInt(document.getElementById("vf-barraca").value);
    const fecha = document.getElementById("vf-fecha").value;
    const notas = document.getElementById("vf-notas").value;

    try {
        await apiPost(`${API}/visitas`, {
            barraca_id: barracaId,
            fecha_planificada: fecha ? new Date(fecha).toISOString() : null,
            notas
        });
        document.getElementById("visita-form").style.display = "none";
        loadVisitas();
    } catch (e) { alert("Error creando visita"); }
}

async function loadVisitas() {
    try {
        const visitas = await apiGet(`${API}/visitas`);
        const container = document.getElementById("visitas-list");
        container.innerHTML = "";

        if (visitas.length === 0) {
            container.innerHTML = '<p style="color:#888;padding:20px;">No hay visitas planificadas</p>';
            return;
        }

        visitas.forEach(v => {
            const div = document.createElement("div");
            div.className = "visita-card";
            const fecha = v.fecha_planificada ? v.fecha_planificada.substring(0, 16).replace("T", " ") : "Sin fecha";
            div.innerHTML = `
                <div class="fecha">📅 ${fecha}</div>
                <div class="barraca">🏗️ ${v.barraca_nombre || "Barraca #" + v.barraca_id}</div>
                <span class="estado estado-${v.estado}">${v.estado}</span>
                ${v.notas ? `<p style="margin-top:5px;color:#666;font-size:0.85em;">${v.notas}</p>` : ""}
                <div class="acciones">
                    ${v.estado === "planificada" ? `
                        <button onclick="realizarVisita(${v.id},'compra')" class="btn-primary" style="padding:4px 10px;font-size:0.8em;">✅ Compra</button>
                        <button onclick="realizarVisita(${v.id},'no_interesa')" style="padding:4px 10px;font-size:0.8em;background:#ccc;border:none;border-radius:4px;cursor:pointer;">❌ No interesa</button>
                        <button onclick="realizarVisita(${v.id},'no_habia_dinero')" style="padding:4px 10px;font-size:0.8em;background:#ffc107;border:none;border-radius:4px;cursor:pointer;">💰 Sin dinero</button>
                    ` : ""}
                </div>
            `;
            container.appendChild(div);
        });
    } catch (e) { console.error("Error cargando visitas:", e); }
}

async function realizarVisita(visitaId, resultado) {
    try {
        await fetch(`${API}/visitas/${visitaId}/realizar?resultado=${resultado}`, { method: "POST", headers: authHeaders() });
        loadVisitas();
    } catch (e) { alert("Error registrando visita"); }
}

function planificarVisita(barracaId) {
    closeModal();
    switchTab("visitas", document.querySelectorAll(".tab")[1]);
    setTimeout(() => {
        showVisitaForm();
        document.getElementById("vf-barraca").value = barracaId;
    }, 100);
}

async function marcarVisitada(barracaId) {
    closeModal();
    // Crear visita rapida realizada
    try {
        const visita = await apiPost(`${API}/visitas`, { barraca_id: barracaId, fecha_planificada: new Date().toISOString() });
        await fetch(`${API}/visitas/${visita.id}/realizar?resultado=compra`, { method: "POST", headers: authHeaders() });
        alert("Visita registrada exitosamente");
    } catch (e) { alert("Error"); }
}

// =============================================
//  CALENDARIO (FullCalendar)
// =============================================

function initCalendario() {
    window.calendarioIniciado = true;
    const el = document.getElementById("calendario");
    if (!el) return;
    
    // FullCalendar desactivado temporalmente por problemas de CDN
    el.innerHTML = '<p style="color:#888;padding:40px;text-align:center;">Calendario temporalmente desactivado.<br>Las visitas se pueden gestionar desde la pestaña "Visitas".</p>';
    return;
    
    /*    
    const calendar = new FullCalendar.Calendar(el, {
        initialView: "dayGridMonth",
        locale: "es",
        headerToolbar: { left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay" },
        events: async (info, success) => {
            try {
                const visitas = await apiGet(`${API}/visitas?fecha_desde=${info.start.toISOString()}&fecha_hasta=${info.end.toISOString()}`);
                const events = visitas.map(v => ({
                    title: v.barraca_nombre || `Barraca #${v.barraca_id}`,
                    start: v.fecha_planificada,
                    color: v.estado === "realizada" ? "#4caf50" : "#e94560"
                }));
                success(events);
            } catch (e) { success([]); }
        },
        eventClick: info => {
            if (info.event.url) window.open(info.event.url);
        }
    });

    calendar.render();
    */
}

// =============================================
//  CALCULADORA DE MATERIALES
// =============================================

function calcularMat() {
    const techo = parseFloat(document.getElementById("c-techo").value) || 0;
    const pared = parseFloat(document.getElementById("c-pared").value) || 0;
    const contra = parseFloat(document.getElementById("c-contra").value) || 0;
    const viga = parseFloat(document.getElementById("c-viga").value) || 0;

    let html = "";
    let resumen = "";

    if (techo > 0) {
        const chapas = Math.ceil(techo / 0.85);  // Chapa acanalada estandar 0.85m util
        const clavos = Math.ceil(chapas / 2);
        document.getElementById("r-techo").textContent = `→ ${chapas} chapas + ~${clavos} kg clavos/tejas`;
        resumen += `- Techo ${techo}m2: ${chapas} chapas acanaladas + ${clavos}kg clavos\n`;
    } else {
        document.getElementById("r-techo").textContent = "";
    }

    if (pared > 0) {
        const ladrillos = Math.ceil(pared * 60);  // 60 ladrillos por m2
        const cemento = Math.ceil(ladrillos / 100);  // 1 bolsa cada 100 ladrillos
        const arena = (pared * 0.05).toFixed(1);  // 50kg arena por m2
        document.getElementById("r-pared").textContent = `→ ${ladrillos} ladrillos + ${cimento} bolsas cemento + ${arena}m3 arena`;
        resumen += `- Pared ${pared}m2: ${ladrillos} ladrillos + ${cimento} bolsas cemento + ${arena}m3 arena\n`;
    } else {
        document.getElementById("r-pared").textContent = "";
    }

    if (contra > 0) {
        const cemento = Math.ceil(contra * 300 / 50);  // 300kg cemento por m3
        const arena = (contra * 0.5).toFixed(2);  // 0.5 m3 arena por m3
        const piedra = (contra * 0.8).toFixed(2);  // 0.8 m3 piedra por m3
        document.getElementById("r-contra").textContent = `→ ${cimento} bolsas cemento + ${arena}m3 arena + ${piedra}m3 piedra`;
        resumen += `- Contrapiso ${contra}m3: ${cimento} bolsas cemento + ${arena}m3 arena + ${piedra}m3 piedra\n`;
    } else {
        document.getElementById("r-contra").textContent = "";
    }

    if (viga > 0) {
        const hierros12 = Math.ceil(viga * 4 * 1.1);  // 4 barras de 12mm por metro + 10% desperdicio
        const hierros8 = Math.ceil(viga * 2 * 1.1);  // 2 estribos de 8mm
        const alambre = Math.ceil(viga * 0.5);
        document.getElementById("r-viga").textContent = `→ ${hierros12} hierros 12mm + ${hierros8} hierros 8mm + ${alambre}kg alambre`;
        resumen += `- Vigas ${viga}ml: ${hierros12} hierros 12mm + ${hierros8} estribos 8mm + ${alambre}kg alambre\n`;
    } else {
        document.getElementById("r-viga").textContent = "";
    }

    if (resumen) {
        document.getElementById("calc-resumen").style.display = "block";
        document.getElementById("calc-resumen-texto").textContent = resumen;
    } else {
        document.getElementById("calc-resumen").style.display = "none";
    }
}

function copiarResumen() {
    const texto = document.getElementById("calc-resumen-texto").textContent;
    navigator.clipboard.writeText(texto).then(() => alert("Copiado al portapapeles"));
}

// =============================================
//  REPORTES
// =============================================

async function loadReportes() {
    try {
        const reporte = await apiGet(`${API}/reportes/diario`);
        document.getElementById("rep-hoy").innerHTML = `
            <div class="stat-box"><div class="stat-num">${reporte.visitas_planificadas}</div><div class="stat-label">Planificadas</div></div>
            <div class="stat-box"><div class="stat-num">${reporte.visitas_realizadas}</div><div class="stat-label">Realizadas</div></div>
            <div class="stat-box"><div class="stat-num">$${reporte.monto_total.toFixed(0)}</div><div class="stat-label">Monto</div></div>
        `;
    } catch (e) { console.error(e); }
}

async function calcularRutaOptima() {
    const ids = allBarracas.filter(b => b.latitude && b.longitude).map(b => b.id);
    if (ids.length < 2) {
        alert("Necesitas al menos 2 barracas con coordenadas para calcular ruta");
        return;
    }

    try {
        const params = ids.map(id => `barraca_ids=${id}`).join("&");
        const result = await apiGet(`${API}/reportes/ruta-optima?${params}`);

        let html = `<p><strong>Distancia total: ${result.total_distance_km} km</strong></p><ol>`;
        result.ordered_barracas.forEach((b, i) => {
            html += `<li>${b.nombre}</li>`;
        });
        html += "</ol>";

        // Dibujar ruta en el mapa
        if (map && result.route_geometry && result.route_geometry.length > 1) {
            const routeLayer = new ol.layer.Vector({
                source: new ol.source.Vector({
                    features: [new ol.Feature({
                        geometry: new ol.geom.LineString(
                            result.route_geometry.map(([lat, lon]) => ol.proj.fromLonLat([lon, lat]))
                        )
                    })]
                }),
                style: new ol.style.Style({ stroke: new ol.style.Stroke({ color: "#e94560", width: 3, lineDash: [8, 4] }) })
            });
            map.addLayer(routeLayer);

            const coords = result.route_geometry.map(([lat, lon]) => ol.proj.fromLonLat([lon, lat]));
            map.getView().fit(ol.extent.boundingExtent(coords), { padding: [50, 50, 50, 50] });

            switchTab("mapa", document.querySelector(".tab"));
        }

        document.getElementById("ruta-result").innerHTML = html;
    } catch (e) { alert("Error calculando ruta"); }
}

// =============================================
//  ADMIN
// =============================================

function showUserForm() {
    document.getElementById("user-form").style.display = "block";
}

async function crearUsuario() {
    const data = {
        username: document.getElementById("uf-username").value,
        password: document.getElementById("uf-password").value,
        nombre_completo: document.getElementById("uf-nombre").value,
        rol: document.getElementById("uf-rol").value
    };
    try {
        await apiPost(`${API}/admin/usuarios`, data);
        document.getElementById("user-form").style.display = "none";
        loadAdminData();
    } catch (e) { alert("Error creando usuario"); }
}

async function loadAdminData() {
    try {
        const users = await apiGet(`${API}/admin/usuarios?solo_activos=false`);
        const asignaciones = await apiGet(`${API}/admin/asignaciones`);

        const uList = document.getElementById("usuarios-list");
        uList.innerHTML = users.map(u => `
            <div class="usuario-card">
                <span><strong>${u.nombre_completo}</strong> (@${u.username}) - ${u.rol} ${u.activo ? "" : " [INACTIVO]"}</span>
                ${u.activo ? `<button onclick="desactivarUsuario(${u.id})" class="btn-danger">Desactivar</button>` : ""}
            </div>
        `).join("");

        const aList = document.getElementById("asignaciones-list");
        aList.innerHTML = asignaciones.map(a => `
            <div class="asignacion-card">
                <span>${a.vendedor_nombre} ↔ ${a.barraca_nombre}</span>
                <button onclick="desasignar(${a.vendedor_id},${a.barraca_id})" class="btn-danger">Quitar</button>
            </div>
        `).join("");

        // Selects de asignacion
        const vendedoresSel = document.getElementById("asig-vendedor");
        const barracasSel = document.getElementById("asig-barraca");
        if (vendedoresSel) vendedoresSel.innerHTML = users.filter(u => u.rol === "vendedor" && u.activo).map(u => `<option value="${u.id}">${u.nombre_completo}</option>`).join("");
        if (barracasSel) barracasSel.innerHTML = allBarracas.map(b => `<option value="${b.id}">${b.nombre}</option>`).join("");

    } catch (e) { console.error("Error admin:", e); }
}

async function desactivarUsuario(id) {
    if (!confirm("Desactivar este usuario?")) return;
    try {
        await apiDelete(`${API}/admin/usuarios/${id}`);
        loadAdminData();
    } catch (e) { alert("Error"); }
}

async function asignarBarracaVendedor() {
    const vendedorId = parseInt(document.getElementById("asig-vendedor").value);
    const barracaId = parseInt(document.getElementById("asig-barraca").value);
    try {
        await apiPost(`${API}/admin/asignaciones`, { vendedor_id: vendedorId, barraca_id: barracaId });
        loadAdminData();
    } catch (e) { alert("Error asignando"); }
}

async function desasignar(vendedorId, barracaId) {
    try {
        await apiDelete(`${API}/admin/asignaciones/${vendedorId}/${barracaId}`);
        loadAdminData();
    } catch (e) { alert("Error"); }
}

// =============================================
//  ARRANQUE
// =============================================

document.addEventListener("DOMContentLoaded", () => {
    // Restaurar sesion si hay token guardado
    const savedToken = localStorage.getItem("bp_token");
    const savedUser = localStorage.getItem("bp_user");

    if (savedToken && savedUser) {
        authToken = savedToken;
        currentUser = JSON.parse(savedUser);
        enterApp();
    }

    // Cerrar modal con click afuera
    document.getElementById("modal-barraca").addEventListener("click", e => {
        if (e.target.id === "modal-barraca") closeModal();
    });
});
