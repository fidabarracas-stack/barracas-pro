/**
 * Barracas Pro v4 - Frontend completo
 * Mapa + Barracas + Visitas + Calculadora
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
    if (currentUser.rol === "admin") document.body.classList.add("is-admin");
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
        </div>`;
    go('mapa', document.querySelector("#nav button"));
}

function go(tab, btn) {
    document.querySelectorAll("#nav button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".view-section").forEach(s => s.classList.remove("active"));
    if (btn) btn.classList.add("active");
    const s = document.getElementById("v-" + tab);
    if (s) s.classList.add("active");
    if (tab === "mapa") {
        setTimeout(initMap, 100);
        // Si el mapa ya existe, actualizar tamaño (puede estar oculto)
        if(map) setTimeout(() => map.updateSize(), 200);
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
    const u = document.getElementById("login-user").value.trim();
    const p = document.getElementById("login-pass").value;
    try {
        const r = await fetch(`${API}/auth/login`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u,password:p})});
        const d = await r.json();
        if (r.ok) { token=d.token; currentUser=d; localStorage.setItem("bp_token",token); render(); }
        else document.getElementById("login-error").textContent = d.detail||"Error";
    } catch(e) { document.getElementById("login-error").textContent = "Error de conexion"; }
}

function doLogout() {
    fetch(`${API}/auth/logout`,{method:"POST",headers:{"Authorization":`Bearer ${token}`}});
    token=null; currentUser=null; localStorage.removeItem("bp_token");
    document.body.classList.remove("is-admin"); render();
}
function authHeaders() { return {"Content-Type":"application/json","Authorization":`Bearer ${token}`}; }

// =============================================
//  MAPA
// =============================================

function initMap() {
    const c = document.getElementById("v-mapa");
    if (!c) return;
    c.innerHTML = `<div id="map-container">
        <aside id="map-sidebar">
            <h3>Mis Barracas</h3>
            <input type="text" id="map-filter" placeholder="Buscar..." onkeyup="filterMap()">
            <div id="map-barracas-list"></div>
            <hr style="border-color:#333;margin:15px 0;">
            <button class="btn btn-primary" onclick="calcularRuta()" style="width:100%;margin-bottom:8px;">🗺️ Ruta Optima</button>
            <div id="ruta-result" style="margin-top:10px;font-size:0.85em;"></div>
        </aside>
        <div id="map-wrap"><div id="map"></div></div>
    </div>`;
    loadMapBarracas();
}

async function loadMapBarracas() {
    try {
        const r = await fetch(`${API}/api/barracas`, {headers:authHeaders()});
        const barracas = await r.json();
        const list = document.getElementById("map-barracas-list");
        const conCoords = barracas.filter(b => b.latitude && b.longitude).length;
        
        list.innerHTML = (conCoords < barracas.length ? 
            `<div style="background:#0f3460;padding:10px;border-radius:6px;margin-bottom:10px;font-size:0.85em;">
                📌 ${conCoords} de ${barracas.length} tienen ubicación. <small style="color:#aaa;">Editá las sin coordenadas para verlas en el mapa.</small>
            </div>` : '') +
            barracas.map(b => `
            <div class="card" onclick="focusBarraca(${b.id},${b.latitude||0},${b.longitude||0})" style="cursor:pointer;${!b.latitude?'opacity:0.6;':''}">
                <div class="title">${b.nombre}</div>
                <div class="subtitle">${b.ciudad||""}<br>${b.telefono||""} ${b.web?b.web.replace(/^https?:\/\//,''):""}</div>
            </div>
        `).join("") || '<p style="color:#888;">Sin barracas</p>';
        
        // Resetear mapa si existe
        if (map) { map.dispose(); map = null; markersLayer = null; routeLayer = null; }
        
        markersLayer = new ol.layer.Vector({
            source: new ol.source.Vector(),
            style: function(feature) {
                return new ol.style.Style({
                    image: new ol.style.Circle({radius:8,fill:new ol.style.Fill({color:'#4caf50'}),stroke:new ol.style.Stroke({color:'#fff',width:2})}),
                    text: new ol.style.Text({text:feature.get('name')||'',font:'bold 11px Segoe UI,Arial,sans-serif',offsetY:-14,fill:new ol.style.Fill({color:'#fff'}),stroke:new ol.style.Stroke({color:'#000',width:3})})
                });
            }
        });
        routeLayer = new ol.layer.Vector({source:new ol.source.Vector(),style:new ol.style.Style({stroke:new ol.style.Stroke({color:"#e94560",width:3,lineDash:[8,4]})})});
        map = new ol.Map({target:"map",layers:[new ol.layer.Tile({source:new ol.source.OSM()}),routeLayer,markersLayer],view:new ol.View({center:ol.proj.fromLonLat([-56.1645,-34.9011]),zoom:12})});
        setTimeout(() => map.updateSize(), 50);
        
        const source = markersLayer.getSource();
        const extent = [];
        barracas.forEach(b => {
            if (b.latitude && b.longitude) {
                source.addFeature(new ol.Feature({geometry:new ol.geom.Point(ol.proj.fromLonLat([b.longitude,b.latitude])),barracaId:b.id,name:b.nombre}));
                extent.push(ol.proj.fromLonLat([b.longitude,b.latitude]));
            }
        });
        if (extent.length > 0) map.getView().fit(ol.extent.boundingExtent(extent),{padding:[40,40,40,40],maxZoom:14});
    } catch(e) { console.error(e); }
}

function focusBarraca(id, lat, lon) { if(lat&&lon) map.getView().animate({center:ol.proj.fromLonLat([lon,lat]),zoom:15}); }
function filterMap() { const q=document.getElementById("map-filter").value.toLowerCase(); document.querySelectorAll("#map-barracas-list .card").forEach(c=>{c.style.display=c.textContent.toLowerCase().includes(q)?"":"none";}); }

async function calcularRuta() {
    try {
        const r = await fetch(`${API}/api/barracas`,{headers:authHeaders()});
        const barracas = await r.json();
        const cc = barracas.filter(b=>b.latitude&&b.longitude);
        if(cc.length<2){document.getElementById("ruta-result").innerHTML="<p style=color:#ff9800;>Necesitas 2+ barracas con coordenadas</p>";return;}
        const ids=cc.map(b=>b.id).join(",");
        const rr = await fetch(`${API}/api/ruta-optima?barraca_ids=${ids}`,{headers:authHeaders()});
        const ruta = await rr.json();
        let h=`<p><strong>📏 ${ruta.total_distance_km} km</strong></p><ol style="padding-left:18px;">`;
        ruta.ordered_barracas.forEach(b=>{h+=`<li>${b.nombre}</li>`;}); h+="</ol>";
        document.getElementById("ruta-result").innerHTML=h;
        routeLayer.getSource().clear();
        if(ruta.route_geometry&&ruta.route_geometry.length>1){const coords=ruta.route_geometry.map(([lat,lon])=>ol.proj.fromLonLat([lon,lat]));routeLayer.getSource().addFeature(new ol.Feature({geometry:new ol.geom.LineString(coords)}));map.getView().fit(ol.extent.boundingExtent(coords),{padding:[50,50,50,50]});}
    } catch(e){console.error(e);}
}

// =============================================
//  VISITAS
// =============================================

async function loadVisitas() {
    const c=document.getElementById("v-visitas");
    c.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h2>Mis Visitas</h2><button class="btn btn-primary" onclick="showVisitaModal()">+ Nueva</button></div><div id="visitas-list"><p style="color:#888;">Cargando...</p></div>`;
    try{const r=await fetch(`${API}/api/visitas`,{headers:authHeaders()});const v=await r.json();const l=document.getElementById("visitas-list");if(!v.length){l.innerHTML='<p style="color:#888;padding:30px;text-align:center;">Sin visitas</p>';return;}l.innerHTML=v.map(x=>`<div class="card"><div class="title">🏗️ ${x.barraca_nombre}</div><div class="subtitle">${x.fecha_planificada?x.fecha_planificada.substring(0,16).replace("T"," "):"Sin fecha"}</div><span class="estado estado-${x.estado}">${x.estado}</span><div class="actions">${x.estado==="planificada"?`<button class="btn btn-success btn-small" onclick="realizarVisita(${x.id},'compra')">✅ Compra</button><button class="btn btn-warning btn-small" onclick="realizarVisita(${x.id},'no_dinero')">💰 Sin dinero</button><button class="btn btn-danger btn-small" onclick="realizarVisita(${x.id},'no_interesa')">❌ No interesa</button>`:""}</div></div>`).join("");}catch(e){document.getElementById("visitas-list").innerHTML='<p style="color:red;">Error</p>';}
}

async function showVisitaModal(){const r=await fetch(`${API}/api/barracas`,{headers:authHeaders()});const b=await r.json();showModal(`<h3>Nueva Visita</h3><select id="vf-barraca"><option value="">Seleccionar...</option>${b.map(x=>`<option value="${x.id}">${x.nombre}</option>`).join("")}</select><input type="datetime-local" id="vf-fecha"><textarea id="vf-notas" placeholder="Notas..."></textarea><div class="actions"><button class="btn btn-primary" onclick="crearVisita()">Guardar</button><button class="btn btn-danger" onclick="hideModal()">Cancelar</button></div>`);}
async function crearVisita(){const b=parseInt(document.getElementById("vf-barraca").value),f=document.getElementById("vf-fecha").value,n=document.getElementById("vf-notas").value;if(!b){alert("Seleccionar barraca");return;}await fetch(`${API}/api/visitas`,{method:"POST",headers:authHeaders(),body:JSON.stringify({barraca_id:b,fecha_planificada:f||null,notas:n})});hideModal();loadVisitas();}
async function realizarVisita(id,res){await fetch(`${API}/api/visitas/${id}/realizar`,{method:"POST",headers:authHeaders(),body:JSON.stringify({resultado:res})});loadVisitas();}

// =============================================
//  BARRACAS (ADMIN)
// =============================================

async function loadBarracas(){
    const c=document.getElementById("v-barracas");
    c.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;"><h2>Gestion de Barracas</h2><div style="display:flex;gap:8px;flex-wrap:wrap;"><button class="btn btn-warning" onclick="importarCafpadu()">🌐 CAFPADU</button><button class="btn btn-info" onclick="document.getElementById('csv-file').click()">📄 CSV</button><button class="btn btn-success" onclick="geocodificarTodas()">📍 Geocodificar</button><button class="btn btn-primary" onclick="showBarracaModal()">+ Nueva</button></div></div><input type="file" id="csv-file" accept=".csv" style="display:none" onchange="importarCSV(event)"><div id="import-status" style="display:none;margin-bottom:15px;padding:12px;background:#0f3460;border-radius:6px;font-size:0.9em;"></div><div id="geo-status" style="display:none;margin-bottom:15px;padding:12px;background:#0f3460;border-radius:6px;font-size:0.9em;"></div><div id="barracas-list"><p style="color:#888;">Cargando...</p></div>`;
    try{const r=await fetch(`${API}/api/barracas`,{headers:authHeaders()});const b=await r.json();const l=document.getElementById("barracas-list");if(!b.length){l.innerHTML='<p style="color:#888;padding:30px;text-align:center;">Sin barracas</p>';return;}l.innerHTML=b.map(x=>`<div class="card"><div class="title">🏗️ ${x.nombre}</div><div class="subtitle">${x.direccion||""} ${x.ciudad||""}<br>${x.telefono?'📞 '+x.telefono:''} ${x.web?'🌐 '+x.web.replace(/^https?:\/\//,''):''} ${x.facebook?'📘':''} ${x.instagram?'📷':''} ${x.whatsapp?'💬':''} ${x.youtube?'▶️':''}</div><div class="actions"><button class="btn btn-primary btn-small" onclick="showBarracaModal(${x.id})">✏️ Editar</button><button class="btn btn-danger btn-small" onclick="deleteBarraca(${x.id})">🗑️</button></div></div>`).join("");}catch(e){document.getElementById("barracas-list").innerHTML='<p style="color:red;">Error</p>';}
}

async function importarCSV(event){
    const file=event.target.files[0];if(!file)return;
    const e=document.getElementById("import-status");e.style.display="block";e.innerHTML="⏳ Procesando CSV...";
    try{const text=await file.text();const res=await fetch(`${API}/admin/importar-csv`,{method:"POST",headers:{"Content-Type":"text/plain","Authorization":`Bearer ${token}`},body:text});const d=await res.json();e.innerHTML=`✅ Importadas: ${d.guardadas||d.saved}, Errores: ${d.errores||0}`;loadBarracas();}catch(x){e.innerHTML="❌ Error procesando CSV";}
    event.target.value="";
}

async function importarCafpadu(){
    if(!confirm("¿Importar desde cafpadu.com.uy?"))return;
    const e=document.getElementById("import-status");e.style.display="block";e.innerHTML="⏳ Importando...";
    try{const r=await fetch(`${API}/admin/importar-cafpadu`,{method:"POST",headers:authHeaders()});const d=await r.json();e.innerHTML=r.ok?`✅ Encontradas: ${d.encontradas}, Guardadas: ${d.guardadas}, Duplicadas: ${d.duplicadas||0}`:`❌ ${d.detail||"Error"}`;loadBarracas();}catch(x){e.innerHTML="❌ Error de conexion";}
}

async function geocodificarTodas(){
    if(!confirm("¿Geocodificar todas las barracas sin coordenadas?"))return;
    const e=document.getElementById("geo-status");e.style.display="block";e.innerHTML="⏳ Geocodificando...";
    try{const r=await fetch(`${API}/admin/geocodificar-todas`,{method:"POST",headers:authHeaders()});const d=await r.json();e.innerHTML=r.ok?`✅ Geocodificadas: ${d.geocodificadas}, Errores: ${d.errores}`:`❌ ${d.detail||"Error"}`;if(map){map.dispose();map=null;markersLayer=null;routeLayer=null;}setTimeout(()=>go('mapa',document.querySelectorAll("#nav button")[0]),100);}catch(x){e.innerHTML="❌ Error de conexion";}
}

async function showBarracaModal(id=null){
    let b={nombre:"",direccion:"",ciudad:"",departamento:"",telefono:"",contacto:"",notas:"",latitude:"",longitude:"",web:"",facebook:"",instagram:"",twitter:"",whatsapp:"",youtube:""};
    if(id){try{const r=await fetch(`${API}/api/barracas/${id}`,{headers:authHeaders()});b=await r.json();}catch(e){alert("Error");return;}}
    showModal(`<h3>${id?"Editar":"Nueva"} Barraca</h3>
    <input type="text" id="b-nombre" placeholder="Nombre *" value="${b.nombre||""}">
    <input type="text" id="b-direccion" placeholder="Direccion" value="${b.direccion||""}">
    <input type="text" id="b-ciudad" placeholder="Ciudad" value="${b.ciudad||""}">
    <input type="text" id="b-departamento" placeholder="Departamento" value="${b.departamento||""}">
    <input type="text" id="b-telefono" placeholder="Telefono" value="${b.telefono||""}">
    <input type="text" id="b-web" placeholder="Pagina web" value="${b.web||""}">
    <input type="text" id="b-facebook" placeholder="Facebook" value="${b.facebook||""}">
    <input type="text" id="b-instagram" placeholder="Instagram" value="${b.instagram||""}">
    <input type="text" id="b-twitter" placeholder="Twitter" value="${b.twitter||""}">
    <input type="text" id="b-whatsapp" placeholder="WhatsApp" value="${b.whatsapp||""}">
    <input type="number" id="b-lat" placeholder="Latitud" value="${b.latitude||""}" step="0.0001">
    <input type="number" id="b-lon" placeholder="Longitud" value="${b.longitude||""}" step="0.0001">
    <textarea id="b-notas" placeholder="Notas">${b.notas||""}</textarea>
    <div class="actions"><button class="btn btn-primary" onclick="saveBarraca(${id})">Guardar</button><button class="btn btn-danger" onclick="hideModal()">Cancelar</button></div>`);
}

async function saveBarraca(id=null){
    const d={nombre:document.getElementById("b-nombre").value.trim(),direccion:document.getElementById("b-direccion").value.trim()||null,ciudad:document.getElementById("b-ciudad").value.trim()||null,departamento:document.getElementById("b-departamento").value.trim()||null,telefono:document.getElementById("b-telefono").value.trim()||null,web:document.getElementById("b-web").value.trim()||null,facebook:document.getElementById("b-facebook").value.trim()||null,instagram:document.getElementById("b-instagram").value.trim()||null,twitter:document.getElementById("b-twitter").value.trim()||null,whatsapp:document.getElementById("b-whatsapp").value.trim()||null,youtube:document.getElementById("b-youtube")?.value.trim()||null,notas:document.getElementById("b-notas").value.trim()||null,latitude:parseFloat(document.getElementById("b-lat").value)||null,longitude:parseFloat(document.getElementById("b-lon").value)||null};
    if(!d.nombre){alert("Nombre obligatorio");return;}
    try{if(id) await fetch(`${API}/api/barracas/${id}`,{method:"PUT",headers:authHeaders(),body:JSON.stringify(d)});else await fetch(`${API}/api/barracas`,{method:"POST",headers:authHeaders(),body:JSON.stringify(d)});hideModal();loadBarracas();}catch(e){alert("Error guardando");}
}

async function deleteBarraca(id){if(!confirm("Eliminar?"))return;await fetch(`${API}/api/barracas/${id}`,{method:"DELETE",headers:authHeaders()});loadBarracas();}

// =============================================
//  USUARIOS (ADMIN)
// =============================================

async function loadUsuarios(){const c=document.getElementById("v-usuarios");c.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h2>Usuarios</h2><button class="btn btn-primary" onclick="showUserModal()">+ Nuevo</button></div><div id="usuarios-list"><p style="color:#888;">Cargando...</p></div>`;try{const r=await fetch(`${API}/admin/usuarios`,{headers:authHeaders()});const u=await r.json();document.getElementById("usuarios-list").innerHTML=u.map(x=>`<div class="card"><div class="title">${x.nombre}</div><div class="subtitle">@${x.username} - ${x.rol} ${!x.activo?"(inactivo)":""}</div></div>`).join("")||'<p style="color:#888;">Sin usuarios</p>';}catch(e){document.getElementById("usuarios-list").innerHTML='<p style="color:red;">Error</p>';}}
function showUserModal(){showModal(`<h3>Nuevo Usuario</h3><input type="text" id="u-username" placeholder="Usuario"><input type="password" id="u-password" placeholder="Contrasena"><input type="text" id="u-nombre" placeholder="Nombre completo"><select id="u-rol"><option value="vendedor">Vendedor</option><option value="admin">Admin</option></select><div class="actions"><button class="btn btn-primary" onclick="createUser()">Crear</button><button class="btn btn-danger" onclick="hideModal()">Cancelar</button></div>`);}
async function createUser(){const d={username:document.getElementById("u-username").value.trim(),password:document.getElementById("u-password").value,nombre:document.getElementById("u-nombre").value.trim(),rol:document.getElementById("u-rol").value};if(!d.username||!d.password||!d.nombre){alert("Completar todos");return;}try{const r=await fetch(`${API}/admin/usuarios`,{method:"POST",headers:authHeaders(),body:JSON.stringify(d)});if(r.ok){hideModal();loadUsuarios();}else{const e=await r.json();alert(e.detail||"Error");}}catch(e){alert("Error");}}

// =============================================
//  ASIGNACIONES (ADMIN)
// =============================================

async function loadAsignaciones(){const c=document.getElementById("v-asignaciones");c.innerHTML=`<h2 style="margin-bottom:15px;">Asignar Barracas a Vendedores</h2><div style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;"><select id="asig-vendedor" style="flex:1;padding:10px;background:#0f3460;color:white;border:1px solid #333;border-radius:6px;"></select><select id="asig-barraca" style="flex:1;padding:10px;background:#0f3460;color:white;border:1px solid #333;border-radius:6px;"></select><button class="btn btn-primary" onclick="asignar()">Asignar</button></div><div id="asig-list"><p style="color:#888;">Cargando...</p></div>`;try{const [ur,br,ar]=await Promise.all([fetch(`${API}/admin/usuarios`,{headers:authHeaders()}),fetch(`${API}/api/barracas`,{headers:authHeaders()}),fetch(`${API}/api/asignaciones`,{headers:authHeaders()})]);const [u,b,a]=await Promise.all([ur.json(),br.json(),ar.json()]);document.getElementById("asig-vendedor").innerHTML=u.filter(x=>x.rol==="vendedor"&&x.activo).map(x=>`<option value="${x.id}">${x.nombre}</option>`).join("");document.getElementById("asig-barraca").innerHTML=b.map(x=>`<option value="${x.id}">${x.nombre}</option>`).join("");document.getElementById("asig-list").innerHTML=a.map(x=>`<div class="card"><div class="title">${x.vendedor_nombre} ↔ ${x.barraca_nombre}</div><div class="actions"><button class="btn btn-danger btn-small" onclick="desasignar(${x.vendedor_id},${x.barraca_id})">Quitar</button></div></div>`).join("")||'<p style="color:#888;">Sin asignaciones</p>';}catch(e){console.error(e);}}
async function asignar(){const v=parseInt(document.getElementById("asig-vendedor").value),b=parseInt(document.getElementById("asig-barraca").value);await fetch(`${API}/api/asignaciones`,{method:"POST",headers:authHeaders(),body:JSON.stringify({vendedor_id:v,barraca_id:b})});loadAsignaciones();}
async function desasignar(v,b){await fetch(`${API}/api/asignaciones`,{method:"DELETE",headers:authHeaders(),body:JSON.stringify({vendedor_id:v,barraca_id:b})});loadAsignaciones();}

// =============================================
//  CALCULADORA, MODAL, INIT
// =============================================

function calcularMat(){
    const t=parseFloat(document.getElementById("c-techo")?.value)||0,p=parseFloat(document.getElementById("c-pared")?.value)||0,ct=parseFloat(document.getElementById("c-contra")?.value)||0,v=parseFloat(document.getElementById("c-viga")?.value)||0;let r="";
    if(t>0){const c=Math.ceil(t/0.85);document.getElementById("r-techo").textContent="→ "+c+" chapas";r+="Techo "+t+"m²: "+c+" chapas\n";}else document.getElementById("r-techo").textContent="";
    if(p>0){const l=Math.ceil(p*60),ce=Math.ceil(l/100);document.getElementById("r-pared").textContent="→ "+l+" ladrillos + "+ce+" bolsas cemento";r+="Pared "+p+"m²: "+l+" ladrillos + "+ce+" bolsas cemento\n";}else document.getElementById("r-pared").textContent="";
    if(ct>0){const ce=Math.ceil(ct*300/50);document.getElementById("r-contra").textContent="→ "+ce+" bolsas cemento";r+="Contrapiso "+ct+"m³: "+ce+" bolsas cemento\n";}else document.getElementById("r-contra").textContent="";
    if(v>0){const h=Math.ceil(v*4*1.1);document.getElementById("r-viga").textContent="→ "+h+" hierros 12mm";r+="Vigas "+v+"ml: "+h+" hierros 12mm\n";}else document.getElementById("r-viga").textContent="";
    if(r){document.getElementById("calc-resumen").style.display="block";document.getElementById("calc-resumen-text").textContent=r;}else document.getElementById("calc-resumen").style.display="none";
}
function copiarResumen(){navigator.clipboard.writeText(document.getElementById("calc-resumen-text").textContent).then(()=>alert("Copiado"));}
function showModal(html){const e=document.querySelector(".modal-bg");if(e)e.remove();const d=document.createElement("div");d.className="modal-bg";d.innerHTML='<div class="modal-box">'+html+"</div>";d.onclick=x=>{if(x.target===d)hideModal();};document.body.appendChild(d);}
function hideModal(){const m=document.querySelector(".modal-bg");if(m)m.remove();}

async function init(){
    if(token){try{const r=await fetch(`${API}/api/barracas`,{headers:authHeaders()});if(r.ok)currentUser={username:"user",nombre:"Usuario",rol:"vendedor",id:0};}catch(e){token=null;localStorage.removeItem("bp_token");}}
    render();
}
document.addEventListener("DOMContentLoaded",init);
