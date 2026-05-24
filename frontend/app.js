/**
 * Barracas Pro v4 - Frontend
 * Login + Barracas + Visitas + Mapa + Rutas
 */
const API = "";
let currentUser = null;
let token = localStorage.getItem("bp_token");
let map, markersLayer, routeLayer;

// =============================================
//  RENDERIZADO
// =============================================

function render() {
    const app = document.getElementById("app");
    if (!currentUser) {
        app.innerHTML = `<div class="login-box">
            <h1>🏗️ Barracas Pro</h1><p>Iniciar sesion</p>
            <input type="text" id="login-user" placeholder="Usuario">
            <input type="password" id="login-pass" placeholder="Contrasena">
            <button onclick="doLogin()">Ingresar</button>
            <div id="login-error" class="error-msg"></div>
        </div>`;
        return;
    }
    
    const isAdmin = currentUser.rol === "admin";
    if (isAdmin) document.body.classList.add("is-admin");
    
    app.innerHTML = `
        <div id="header">
            <span class="logo">🏗️ Barracas Pro</span>
            <div class="user-info">
                <span>${currentUser.nombre} (${currentUser.rol})</span>
                <button class="btn-logout" onclick="doLogout()">Salir</button>
            </div>
        </div>
        <nav id="nav">
            <button class="active" onclick="go('mapa',this)">🗺️ Mapa</button>
            <button onclick="go('visitas',this)">📅 Visitas</button>
            <button onclick="go('calculadora',this)">🧮 Calc</button>
            <button class="admin-only" onclick="go('barracas',this)">🏗️ Barracas</button>
            <button class="admin-only" onclick="go('usuarios',this)">👤 Usuarios</button>
            <button class="admin-only" onclick="go('asignaciones',this)">🔗 Asignar</button>
        </nav>
        <div id="content">
            <section id="v-mapa" class="view-section active"></section>
            <section id="v-visitas" class="view-section"></section>
            <section id="v-calculadora" class="view-section"></section>
            <section id="v-barracas" class="view-section"></section>
            <section id="v-usuarios" class="view-section"></section>
            <section id="v-asignaciones" class="view-section"></section>
        </div>
    `;
    go('mapa', document.querySelector("#nav button"));
}

function go(tab, btn) {
    document.querySelectorAll("#nav button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".view-section").forEach(s => s.classList.remove("active"));
    if (btn) btn.classList.add("active");
    const section = document.getElementById("v-" + tab);
    if (section) section.classList.add("active");
    
    if (tab === "mapa") {
        if (map) {
            // Mapa ya existe, solo actualizar tamano
            setTimeout(() => { map.updateSize(); }, 50);
        } else {
            setTimeout(initMap, 100);
        }
    }
    if (tab === "visitas") loadVisitas();
    if (tab === "barracas") loadBarracas();
    if (tab === "usuarios") loadUsuarios();
    if (tab === "asignaciones") loadAsignaciones();
}

// =============================================
//  AUTH
// =============================================

async function doLogin() {
    const username = document.getElementById("login-user").value.trim();
    const password = document.getElementById("login-pass").value;
    try {
        const res = await fetch(`${API}/auth/login`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({username, password})
        });
        const data = await res.json();
        if (res.ok) {
            token = data.token;
            currentUser = data;
            localStorage.setItem("bp_token", token);
            render();
        } else {
            document.getElementById("login-error").textContent = data.detail || "Error";
        }
    } catch (e) {
        document.getElementById("login-error").textContent = "Error de conexion";
    }
}

function doLogout() {
    fetch(`${API}/auth/logout`, {method: "POST", headers: {"Authorization": `Bearer ${token}`}});
    token = null; currentUser = null;
    localStorage.removeItem("bp_token");
    document.body.classList.remove("is-admin");
    render();
}

function authHeaders() {
    return {"Content-Type": "application/json", "Authorization": `Bearer ${token}`};
}

// =============================================
//  MAPA
// =============================================

function initMap() {
    const container = document.getElementById("v-mapa");
    container.innerHTML = `
        <div id="map-container">
            <aside id="map-sidebar">
                <h3>Mis Barracas</h3>
                <input type="text" id="map-filter" placeholder="Buscar..." onkeyup="filterMap()">
                <div id="map-barracas-list"></div>
                <hr style="border-color:#333;margin:15px 0;">
                <button class="btn btn-primary" onclick="calcularRuta()" style="width:100%;">🗺️ Ruta Optima</button>
                <div id="ruta-result" style="margin-top:10px;font-size:0.85em;"></div>
            </aside>
            <div id="map-wrap"><div id="map"></div></div>
        </div>`;
    
    loadMapBarracas();
}

async function loadMapBarracas() {
    try {
        const res = await fetch(`${API}/api/barracas`, {headers: authHeaders()});
        const barracas = await res.json();
        
        const listEl = document.getElementById("map-barracas-list");
        listEl.innerHTML = barracas.map(b => `
            <div class="card" onclick="focusBarraca(${b.id},${b.latitude||0},${b.longitude||0})">
                <div class="title">${b.nombre}</div>
                <div class="subtitle">${b.ciudad || ""} ${b.telefono || ""}</div>
            </div>
        `).join("") || '<p style="color:#888;font-size:0.9em;">Sin barracas</p>';
        
        // Inicializar mapa
        if (map) return;
        
        markersLayer = new ol.layer.Vector({
            source: new ol.source.Vector(),
            style: f => {
                const sel = f.get("selected");
                return new ol.style.Style({
                    image: new ol.style.Circle({radius: 8, fill: new ol.style.Fill({color: sel ? "#2196F3" : "#4caf50"}), stroke: new ol.style.Stroke({color: "#fff", width: 2})}),
                    text: new ol.style.Text({text: f.get("name"), font: "11px sans-serif", offsetY: -14, fill: new ol.style.Fill({color: "#fff"}), stroke: new ol.style.Stroke({color: "#000", width: 3})})
                });
            }
        });
        
        routeLayer = new ol.layer.Vector({
            source: new ol.source.Vector(),
            style: new ol.style.Style({stroke: new ol.style.Stroke({color: "#e94560", width: 3, lineDash: [8, 4]})})
        });
        
        map = new ol.Map({
            target: "map",
            layers: [new ol.layer.Tile({source: new ol.source.OSM()}), routeLayer, markersLayer],
            view: new ol.View({center: ol.proj.fromLonLat([-56.1645, -34.9011]), zoom: 12})
        });
        
        // Agregar marcadores
        const source = markersLayer.getSource();
        source.clear();
        const extent = [];
        barracas.forEach(b => {
            if (b.latitude && b.longitude) {
                const f = new ol.Feature({
                    geometry: new ol.geom.Point(ol.proj.fromLonLat([b.longitude, b.latitude])),
                    barracaId: b.id, name: b.nombre, selected: false
                });
                source.addFeature(f);
                extent.push(ol.proj.fromLonLat([b.longitude, b.latitude]));
            }
        });
        if (extent.length > 0) {
            map.getView().fit(ol.extent.boundingExtent(extent), {padding: [40, 40, 40, 40], maxZoom: 14});
        }
    } catch (e) { console.error(e); }
}

function focusBarraca(id, lat, lon) {
    if (lat && lon) {
        map.getView().animate({center: ol.proj.fromLonLat([lon, lat]), zoom: 15});
    }
}

function filterMap() {
    const q = document.getElementById("map-filter").value.toLowerCase();
    document.querySelectorAll("#map-barracas-list .card").forEach(c => {
        c.style.display = c.textContent.toLowerCase().includes(q) ? "" : "none";
    });
}

async function calcularRuta() {
    try {
        const res = await fetch(`${API}/api/barracas`, {headers: authHeaders()});
        const barracas = await res.json();
        const conCoordenadas = barracas.filter(b => b.latitude && b.longitude);
        
        if (conCoordenadas.length < 2) {
            document.getElementById("ruta-result").innerHTML = "<p style=color:#ff9800;>Necesitas al menos 2 barracas con coordenadas</p>";
            return;
        }
        
        const ids = conCoordenadas.map(b => b.id).join(",");
        const rutaRes = await fetch(`${API}/api/ruta-optima?barraca_ids=${ids}`, {headers: authHeaders()});
        const ruta = await rutaRes.json();
        
        let html = `<p><strong>📏 ${ruta.total_distance_km} km</strong></p><ol style="padding-left:18px;">`;
        ruta.ordered_barracas.forEach((b, i) => {
            html += `<li>${b.nombre}</li>`;
        });
        html += "</ol>";
        document.getElementById("ruta-result").innerHTML = html;
        
        // Dibujar ruta
        routeLayer.getSource().clear();
        if (ruta.route_geometry && ruta.route_geometry.length > 1) {
            const coords = ruta.route_geometry.map(([lat, lon]) => ol.proj.fromLonLat([lon, lat]));
            routeLayer.getSource().addFeature(new ol.Feature({geometry: new ol.geom.LineString(coords)}));
            map.getView().fit(ol.extent.boundingExtent(coords), {padding: [50, 50, 50, 50]});
        }
    } catch (e) { console.error(e); }
}

// =============================================
//  VISITAS
// =============================================

async function loadVisitas() {
    const container = document.getElementById("v-visitas");
    container.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2>Mis Visitas</h2>
            <button class="btn btn-primary" onclick="showNewVisitaModal()">+ Nueva Visita</button>
        </div>
        <div id="visitas-list"><p style="color:#888;">Cargando...</p></div>
    `;
    
    try {
        const res = await fetch(`${API}/api/visitas`, {headers: authHeaders()});
        const visitas = await res.json();
        
        const listEl = document.getElementById("visitas-list");
        if (visitas.length === 0) {
            listEl.innerHTML = '<p style="color:#888;padding:30px;text-align:center;">No hay visitas planificadas</p>';
            return;
        }
        
        listEl.innerHTML = visitas.map(v => `
            <div class="card">
                <div class="title">🏗️ ${v.barraca_nombre}</div>
                <div class="subtitle">${v.fecha_planificada ? v.fecha_planificada.substring(0,16).replace("T"," ") : "Sin fecha"}</div>
                <span class="estado estado-${v.estado}">${v.estado}</span>
                ${v.notas ? `<p style="margin-top:8px;color:#aaa;font-size:0.85em;">${v.notas}</p>` : ""}
                <div class="actions">
                    ${v.estado === "planificada" ? `
                        <button class="btn btn-success btn-small" onclick="realizarVisita(${v.id},'compra')">✅ Compra</button>
                        <button class="btn btn-warning btn-small" onclick="realizarVisita(${v.id},'no_dinero')">💰 Sin dinero</button>
                        <button class="btn btn-danger btn-small" onclick="realizarVisita(${v.id},'no_interesa')">❌ No interesa</button>
                    ` : ""}
                </div>
            </div>
        `).join("");
    } catch (e) {
        document.getElementById("visitas-list").innerHTML = '<p style="color:red;">Error cargando visitas</p>';
    }
}

async function showNewVisitaModal() {
    try {
        const res = await fetch(`${API}/api/barracas`, {headers: authHeaders()});
        const barracas = await res.json();
        
        const options = barracas.map(b => `<option value="${b.id}">${b.nombre}</option>`).join("");
        
        showModal(`
            <h3>Nueva Visita</h3>
            <select id="visita-barraca"><option value="">Seleccionar barraca...</option>${options}</select>
            <input type="datetime-local" id="visita-fecha">
            <textarea id="visita-notas" placeholder="Notas..."></textarea>
            <div class="actions">
                <button class="btn btn-primary" onclick="crearVisita()">Guardar</button>
                <button class="btn btn-danger" onclick="hideModal()">Cancelar</button>
            </div>
        `);
    } catch (e) { alert("Error cargando barracas"); }
}

async function crearVisita() {
    const barraca_id = parseInt(document.getElementById("visita-barraca").value);
    const fecha = document.getElementById("visita-fecha").value;
    const notas = document.getElementById("visita-notas").value;
    
    if (!barraca_id) { alert("Seleccionar una barraca"); return; }
    
    try {
        await fetch(`${API}/api/visitas`, {
            method: "POST", headers: authHeaders(),
            body: JSON.stringify({barraca_id, fecha_planificada: fecha || null, notas})
        });
        hideModal();
        loadVisitas();
    } catch (e) { alert("Error creando visita"); }
}

async function realizarVisita(visitaId, resultado) {
    try {
        await fetch(`${API}/api/visitas/${visitaId}/realizar`, {
            method: "POST", headers: authHeaders(),
            body: JSON.stringify({resultado})
        });
        loadVisitas();
    } catch (e) { alert("Error"); }
}

// =============================================
//  BARRACAS (admin)
// =============================================

async function loadBarracas() {
    const container = document.getElementById("v-barracas");
    container.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
            <h2>Gestion de Barracas</h2>
            <div style="display:flex;gap:8px;">
                <button class="btn btn-warning" onclick="importarCafpadu()">🌐 Importar desde CAFPADU</button>
                <button class="btn btn-primary" onclick="showBarracaModal()">+ Nueva Barraca</button>
            </div>
        </div>
        <div id="import-status" style="display:none;margin-bottom:15px;padding:12px;background:#0f3460;border-radius:6px;font-size:0.9em;"></div>
        <div id="barracas-list"><p style="color:#888;">Cargando...</p></div>
    `;
    
    try {
        const res = await fetch(`${API}/api/barracas`, {headers: authHeaders()});
        const barracas = await res.json();
        
        const listEl = document.getElementById("barracas-list");
        if (barracas.length === 0) {
            listEl.innerHTML = '<p style="color:#888;padding:30px;text-align:center;">No hay barracas cargadas</p>';
            return;
        }
        
        listEl.innerHTML = barracas.map(b => `
            <div class="card">
                <div class="title">🏗️ ${b.nombre}</div>
                <div class="subtitle">${b.direccion || ""} ${b.ciudad || ""} ${b.telefono || ""}</div>
                <div class="actions">
                    <button class="btn btn-primary btn-small" onclick="showBarracaModal(${b.id})">✏️ Editar</button>
                    <button class="btn btn-danger btn-small" onclick="deleteBarraca(${b.id})">🗑️ Eliminar</button>
                </div>
            </div>
        `).join("");
    } catch (e) {
        document.getElementById("barracas-list").innerHTML = '<p style="color:red;">Error</p>';
    }
}

async function showBarracaModal(barracaId = null) {
    let barraca = {nombre: "", direccion: "", ciudad: "", departamento: "", telefono: "", contacto: "", notas: "", latitude: "", longitude: ""};
    
    if (barracaId) {
        try {
            const res = await fetch(`${API}/api/barracas/${barracaId}`, {headers: authHeaders()});
            barraca = await res.json();
        } catch (e) { alert("Error cargando barraca"); return; }
    }
    
    showModal(`
        <h3>${barracaId ? "Editar" : "Nueva"} Barraca</h3>
        <input type="text" id="b-nombre" placeholder="Nombre *" value="${barraca.nombre || ""}">
        <input type="text" id="b-direccion" placeholder="Direccion" value="${barraca.direccion || ""}">
        <input type="text" id="b-ciudad" placeholder="Ciudad" value="${barraca.ciudad || ""}">
        <input type="text" id="b-departamento" placeholder="Departamento" value="${barraca.departamento || ""}">
        <input type="text" id="b-telefono" placeholder="Telefono" value="${barraca.telefono || ""}">
        <input type="text" id="b-contacto" placeholder="Contacto" value="${barraca.contacto || ""}">
        <input type="number" id="b-lat" placeholder="Latitud" value="${barraca.latitude || ""}" step="0.0001">
        <input type="number" id="b-lon" placeholder="Longitud" value="${barraca.longitude || ""}" step="0.0001">
        <textarea id="b-notas" placeholder="Notas">${barraca.notas || ""}</textarea>
        <div class="actions">
            <button class="btn btn-primary" onclick="saveBarraca(${barracaId})">Guardar</button>
            <button class="btn btn-danger" onclick="hideModal()">Cancelar</button>
        </div>
    `);
}

async function saveBarraca(barracaId = null) {
    const data = {
        nombre: document.getElementById("b-nombre").value.trim(),
        direccion: document.getElementById("b-direccion").value.trim() || null,
        ciudad: document.getElementById("b-ciudad").value.trim() || null,
        departamento: document.getElementById("b-departamento").value.trim() || null,
        telefono: document.getElementById("b-telefono").value.trim() || null,
        contacto: document.getElementById("b-contacto").value.trim() || null,
        notas: document.getElementById("b-notas").value.trim() || null,
        latitude: parseFloat(document.getElementById("b-lat").value) || null,
        longitude: parseFloat(document.getElementById("b-lon").value) || null
    };
    
    if (!data.nombre) { alert("Nombre obligatorio"); return; }
    
    try {
        if (barracaId) {
            await fetch(`${API}/api/barracas/${barracaId}`, {method: "PUT", headers: authHeaders(), body: JSON.stringify(data)});
        } else {
            await fetch(`${API}/api/barracas`, {method: "POST", headers: authHeaders(), body: JSON.stringify(data)});
        }
        hideModal();
        loadBarracas();
    } catch (e) { alert("Error guardando"); }
}

async function deleteBarraca(id) {
    if (!confirm("Eliminar esta barraca?")) return;
    try {
        await fetch(`${API}/api/barracas/${id}`, {method: "DELETE", headers: authHeaders()});
        loadBarracas();
    } catch (e) { alert("Error eliminando"); }
}

// =============================================
//  IMPORTACION DESDE CAFPADU
// =============================================

async function importarCafpadu() {
    if (!confirm("¿Importar barracas desde cafpadu.com.uy?\n\nEsto puede tardar varios minutos.")) return;
    
    const statusEl = document.getElementById("import-status");
    statusEl.style.display = "block";
    statusEl.innerHTML = "⏳ Importando... Esto puede tardar varios minutos. No cierres esta página.";
    
    try {
        const res = await fetch(`${API}/admin/importar-cafpadu`, {
            method: "POST",
            headers: authHeaders()
        });
        const data = await res.json();
        
        if (res.ok) {
            statusEl.innerHTML = `✅ <strong>Importación completada</strong><br>Encontradas: ${data.encontradas}<br>Guardadas: ${data.guardadas}<br><small style="color:#aaa;">Duplicadas (saltadas): ${data.duplicadas || 0}</small>`;
            loadBarracas();
        } else {
            statusEl.innerHTML = `❌ Error: ${data.detail || "Error desconocido"}`;
        }
    } catch (e) {
        statusEl.innerHTML = "❌ Error de conexión. El servidor puede estar ocupado. Intentá de nuevo.";
    }
}

// =============================================
//  USUARIOS (admin)
// =============================================

async function loadUsuarios() {
    const container = document.getElementById("v-usuarios");
    container.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2>Usuarios del Equipo</h2>
            <button class="btn btn-primary" onclick="showUserModal()">+ Nuevo Usuario</button>
        </div>
        <div id="usuarios-list"><p style="color:#888;">Cargando...</p></div>
    `;
    
    try {
        const res = await fetch(`${API}/admin/usuarios`, {headers: authHeaders()});
        const users = await res.json();
        
        document.getElementById("usuarios-list").innerHTML = users.map(u => `
            <div class="card">
                <div class="title">${u.nombre}</div>
                <div class="subtitle">@${u.username} - ${u.rol} ${!u.activo ? "(inactivo)" : ""}</div>
            </div>
        `).join("") || '<p style="color:#888;">Sin usuarios</p>';
    } catch (e) {
        document.getElementById("usuarios-list").innerHTML = '<p style="color:red;">Error</p>';
    }
}

function showUserModal() {
    showModal(`
        <h3>Nuevo Usuario</h3>
        <input type="text" id="u-username" placeholder="Usuario">
        <input type="password" id="u-password" placeholder="Contrasena">
        <input type="text" id="u-nombre" placeholder="Nombre completo">
        <select id="u-rol"><option value="vendedor">Vendedor</option><option value="admin">Admin</option></select>
        <div class="actions">
            <button class="btn btn-primary" onclick="createUser()">Crear</button>
            <button class="btn btn-danger" onclick="hideModal()">Cancelar</button>
        </div>
    `);
}

async function createUser() {
    const data = {
        username: document.getElementById("u-username").value.trim(),
        password: document.getElementById("u-password").value,
        nombre: document.getElementById("u-nombre").value.trim(),
        rol: document.getElementById("u-rol").value
    };
    if (!data.username || !data.password || !data.nombre) { alert("Completar todos"); return; }
    
    try {
        const res = await fetch(`${API}/admin/usuarios`, {method: "POST", headers: authHeaders(), body: JSON.stringify(data)});
        if (res.ok) { hideModal(); loadUsuarios(); }
        else { const e = await res.json(); alert(e.detail || "Error"); }
    } catch (e) { alert("Error de conexion"); }
}

// =============================================
//  ASIGNACIONES (admin)
// =============================================

async function loadAsignaciones() {
    const container = document.getElementById("v-asignaciones");
    container.innerHTML = `
        <h2 style="margin-bottom:15px;">Asignar Barracas a Vendedores</h2>
        <div id="asig-form" style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;">
            <select id="asig-vendedor" style="flex:1;padding:10px;background:#0f3460;color:white;border:1px solid #333;border-radius:6px;"></select>
            <select id="asig-barraca" style="flex:1;padding:10px;background:#0f3460;color:white;border:1px solid #333;border-radius:6px;"></select>
            <button class="btn btn-primary" onclick="asignar()">Asignar</button>
        </div>
        <div id="asig-list"><p style="color:#888;">Cargando...</p></div>
    `;
    
    try {
        const [usersRes, barracasRes, asigRes] = await Promise.all([
            fetch(`${API}/admin/usuarios`, {headers: authHeaders()}),
            fetch(`${API}/api/barracas`, {headers: authHeaders()}),
            fetch(`${API}/api/asignaciones`, {headers: authHeaders()})
        ]);
        
        const users = await usersRes.json();
        const barracas = await barracasRes.json();
        const asignaciones = await asigRes.json();
        
        document.getElementById("asig-vendedor").innerHTML = users.filter(u => u.rol === "vendedor" && u.activo).map(u => `<option value="${u.id}">${u.nombre}</option>`).join("");
        document.getElementById("asig-barraca").innerHTML = barracas.map(b => `<option value="${b.id}">${b.nombre}</option>`).join("");
        
        document.getElementById("asig-list").innerHTML = asignaciones.map(a => `
            <div class="card">
                <div class="title">${a.vendedor_nombre} ↔ ${a.barraca_nombre}</div>
                <div class="actions">
                    <button class="btn btn-danger btn-small" onclick="desasignar(${a.vendedor_id},${a.barraca_id})">Quitar</button>
                </div>
            </div>
        `).join("") || '<p style="color:#888;">Sin asignaciones</p>';
    } catch (e) { console.error(e); }
}

async function asignar() {
    const vendedor_id = parseInt(document.getElementById("asig-vendedor").value);
    const barraca_id = parseInt(document.getElementById("asig-barraca").value);
    try {
        await fetch(`${API}/api/asignaciones`, {method: "POST", headers: authHeaders(), body: JSON.stringify({vendedor_id, barraca_id})});
        loadAsignaciones();
    } catch (e) { alert("Error"); }
}

async function desasignar(vid, bid) {
    try {
        await fetch(`${API}/api/asignaciones`, {method: "DELETE", headers: authHeaders(), body: JSON.stringify({vendedor_id: vid, barraca_id: bid})});
        loadAsignaciones();
    } catch (e) { alert("Error"); }
}

// =============================================
//  CALCULADORA
// =============================================

function calcularMat() {
    const techo = parseFloat(document.getElementById("c-techo")?.value) || 0;
    const pared = parseFloat(document.getElementById("c-pared")?.value) || 0;
    const contra = parseFloat(document.getElementById("c-contra")?.value) || 0;
    const viga = parseFloat(document.getElementById("c-viga")?.value) || 0;
    
    let resumen = "";
    
    if (techo > 0) {
        const chapas = Math.ceil(techo / 0.85);
        document.getElementById("r-techo").textContent = `→ ${chapas} chapas`;
        resumen += `- Techo ${techo}m²: ${chapas} chapas\n`;
    } else { document.getElementById("r-techo").textContent = ""; }
    
    if (pared > 0) {
        const ladrillos = Math.ceil(pared * 60);
        const cemento = Math.ceil(ladrillos / 100);
        document.getElementById("r-pared").textContent = `→ ${ladrillos} ladrillos + ${cimento} bolsas cemento`;
        resumen += `- Pared ${pared}m²: ${ladrillos} ladrillos + ${cimento} bolsas cemento\n`;
    } else { document.getElementById("r-pared").textContent = ""; }
    
    if (contra > 0) {
        const cemento = Math.ceil(contra * 300 / 50);
        document.getElementById("r-contra").textContent = `→ ${cimento} bolsas cemento`;
        resumen += `- Contrapiso ${contra}m³: ${cimento} bolsas cemento\n`;
    } else { document.getElementById("r-contra").textContent = ""; }
    
    if (viga > 0) {
        const hierros = Math.ceil(viga * 4 * 1.1);
        document.getElementById("r-viga").textContent = `→ ${hierros} hierros 12mm`;
        resumen += `- Vigas ${viga}ml: ${hierros} hierros 12mm\n`;
    } else { document.getElementById("r-viga").textContent = ""; }
    
    if (resumen) {
        document.getElementById("calc-resumen").style.display = "block";
        document.getElementById("calc-resumen-text").textContent = resumen;
    } else {
        document.getElementById("calc-resumen").style.display = "none";
    }
}

function copiarResumen() {
    const t = document.getElementById("calc-resumen-text").textContent;
    navigator.clipboard.writeText(t).then(() => alert("Copiado"));
}

// =============================================
//  MODAL + UTILIDADES
// =============================================

function showModal(html) {
    const existing = document.querySelector(".modal-bg");
    if (existing) existing.remove();
    
    const div = document.createElement("div");
    div.className = "modal-bg";
    div.innerHTML = `<div class="modal-box">${html}</div>`;
    div.onclick = e => { if (e.target === div) hideModal(); };
    document.body.appendChild(div);
}

function hideModal() {
    const m = document.querySelector(".modal-bg");
    if (m) m.remove();
}

// =============================================
//  ARRANQUE
// =============================================

async function init() {
    if (token) {
        try {
            const res = await fetch(`${API}/api/barracas`, {headers: authHeaders()});
            if (res.ok) {
                currentUser = {username: "user", nombre: "Usuario", rol: "vendedor", id: 0};
            }
        } catch (e) {
            token = null;
            localStorage.removeItem("bp_token");
        }
    }
    render();
}

document.addEventListener("DOMContentLoaded", init);
