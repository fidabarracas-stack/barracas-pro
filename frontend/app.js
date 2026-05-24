/**
 * Barracas Pro v3 - Frontend minimo
 * Login + Admin de usuarios
 */
const API = "";

let currentUser = null;
let token = localStorage.getItem("bp_token");

// =============================================
//  RENDERIZADO POR VISTAS
// =============================================

function render() {
    const app = document.getElementById("app");
    
    if (!currentUser) {
        app.innerHTML = `
            <div class="login-box">
                <h1>🏗️ Barracas Pro</h1>
                <p>Iniciar sesion</p>
                <input type="text" id="login-user" placeholder="Usuario">
                <input type="password" id="login-pass" placeholder="Contrasena">
                <button onclick="doLogin()">Ingresar</button>
                <div id="login-error" class="error-msg"></div>
            </div>`;
    } else if (currentUser.rol === "admin") {
        renderAdmin(app);
    } else {
        renderVendedor(app);
    }
}

function renderAdmin(container) {
    container.innerHTML = `
        <div id="header">
            <span class="logo">🏗️ Barracas Pro</span>
            <div class="user-info">
                <span>${currentUser.nombre} (admin)</span>
                <button class="btn-logout" onclick="doLogout()">Salir</button>
            </div>
        </div>
        <div class="admin-container">
            <h2>👤 Usuarios del equipo</h2>
            <button class="btn-new" onclick="showNewUserModal()">+ Nuevo Usuario</button>
            <div id="users-list"><p style="color:#888;">Cargando...</p></div>
        </div>
        <div id="modal" class="modal hidden">
            <div class="modal-box">
                <h3>Nuevo Usuario</h3>
                <input type="text" id="new-username" placeholder="Usuario">
                <input type="password" id="new-password" placeholder="Contrasena">
                <input type="text" id="new-nombre" placeholder="Nombre completo">
                <select id="new-rol">
                    <option value="vendedor">Vendedor</option>
                    <option value="admin">Admin</option>
                </select>
                <div class="actions">
                    <button class="btn-save" onclick="createUser()">Crear</button>
                    <button class="btn-cancel" onclick="hideModal()">Cancelar</button>
                </div>
            </div>
        </div>`;
    loadUsers();
}

function renderVendedor(container) {
    container.innerHTML = `
        <div id="header">
            <span class="logo">🏗️ Barracas Pro</span>
            <div class="user-info">
                <span>${currentUser.nombre}</span>
                <button class="btn-logout" onclick="doLogout()">Salir</button>
            </div>
        </div>
        <div class="admin-container">
            <h2>👋 Bienvenido, ${currentUser.nombre}</h2>
            <p style="color:#aaa;margin-top:10px;">Sistema de gestion de barracas.<br>Proximamente: mapa, visitas, rutas.</p>
        </div>`;
}

// =============================================
//  FUNCIONES
// =============================================

async function doLogin() {
    const username = document.getElementById("login-user").value.trim();
    const password = document.getElementById("login-pass").value;
    const errorEl = document.getElementById("login-error");
    
    try {
        const res = await fetch(`${API}/auth/login`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({username, password})
        });
        const data = await res.json();
        if (res.ok) {
            token = data.token;
            currentUser = data;
            localStorage.setItem("bp_token", token);
            render();
        } else {
            errorEl.textContent = data.detail || "Error de login";
        }
    } catch (e) {
        errorEl.textContent = "Error de conexion";
    }
}

function doLogout() {
    fetch(`${API}/auth/logout`, {
        method: "POST",
        headers: {"Authorization": `Bearer ${token}`}
    });
    token = null;
    currentUser = null;
    localStorage.removeItem("bp_token");
    render();
}

async function loadUsers() {
    try {
        const res = await fetch(`${API}/admin/usuarios`, {
            headers: {"Authorization": `Bearer ${token}`}
        });
        const users = await res.json();
        const container = document.getElementById("users-list");
        if (users.length === 0) {
            container.innerHTML = '<p style="color:#888;">No hay usuarios creados</p>';
            return;
        }
        container.innerHTML = users.map(u => `
            <div class="user-card">
                <div>
                    <strong>${u.nombre}</strong>
                    <br><small style="color:#888;">@${u.username}</small>
                </div>
                <span class="rol">${u.rol}</span>
            </div>
        `).join("");
    } catch (e) {
        document.getElementById("users-list").innerHTML = '<p style="color:#ff6b6b;">Error cargando usuarios</p>';
    }
}

function showNewUserModal() {
    document.getElementById("modal").classList.remove("hidden");
}

function hideModal() {
    document.getElementById("modal").classList.add("hidden");
}

async function createUser() {
    const data = {
        username: document.getElementById("new-username").value.trim(),
        password: document.getElementById("new-password").value,
        nombre: document.getElementById("new-nombre").value.trim(),
        rol: document.getElementById("new-rol").value
    };
    if (!data.username || !data.password || !data.nombre) {
        alert("Completar todos los campos");
        return;
    }
    try {
        const res = await fetch(`${API}/admin/usuarios`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            hideModal();
            loadUsers();
        } else {
            const err = await res.json();
            alert(err.detail || "Error creando usuario");
        }
    } catch (e) {
        alert("Error de conexion");
    }
}

// =============================================
//  ARRANQUE
// =============================================

async function init() {
    // Si hay token, verificar que sea valido
    if (token) {
        try {
            const res = await fetch(`${API}/admin/usuarios`, {
                headers: {"Authorization": `Bearer ${token}`}
            });
            if (res.ok) {
                currentUser = {username: "admin", nombre: "Admin", rol: "admin"};
            }
        } catch (e) {
            token = null;
            localStorage.removeItem("bp_token");
        }
    }
    render();
}

document.addEventListener("DOMContentLoaded", init);
