import re

file_path = "d:/service_kawaii/feedback/static/css/admin.css"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

start_idx = content.find("@media (max-width: 768px) {")
if start_idx != -1:
    new_media_query = """@media (max-width: 768px) {

    /* ==============================================================
       MOBILE REDESIGN (Minimalist / Tailwind-inspired)
       ============================================================== */

    /* 1. Base Reset & Typography */
    html, body {
        width: 100% !important;
        overflow-x: hidden !important;
        background-color: #0f172a !important; /* slate-900 */
        color: #f8fafc !important; /* slate-50 */
        font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        padding-bottom: 90px !important; /* Space for bottom nav */
    }

    *, *::before, *::after {
        box-sizing: border-box !important;
        max-width: 100vw !important; /* Prevent horizontal overflow */
    }

    /* 2. Layout Wrappers */
    .saas-centered-wrapper, .saas-container, .saas-content, .saas-panel-body {
        display: block !important;
        width: 100% !important;
        height: auto !important;
        min-height: auto !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }

    /* 3. Header & Search */
    .saas-header {
        padding: 16px 20px 0 20px !important;
        margin-bottom: 24px !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 16px !important;
    }

    .saas-header-right {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
    }

    .saas-clock { display: none !important; }
    .saas-profile-avatar { display: none !important; }

    .saas-profile-widget {
        display: flex !important;
        align-items: center !important;
        padding: 0 !important;
        border: none !important;
        background: transparent !important;
    }

    .saas-username {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
    }

    .saas-role {
        font-size: 12px !important;
        color: #94a3b8 !important; /* slate-400 */
        font-weight: 500 !important;
    }

    .saas-search-container {
        width: 100% !important;
        height: 48px !important;
        background-color: #1e293b !important; /* slate-800 */
        border: 1px solid #334155 !important; /* slate-700 */
        border-radius: 12px !important;
        position: relative !important;
    }

    .saas-search-input {
        width: 100% !important;
        height: 100% !important;
        padding: 0 16px 0 44px !important;
        font-size: 15px !important;
        background: transparent !important;
        border: none !important;
        color: #f8fafc !important;
        border-radius: 12px !important;
    }

    .saas-search-input::placeholder {
        color: #64748b !important; /* slate-500 */
    }

    .saas-search-icon {
        position: absolute !important;
        left: 16px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        color: #64748b !important;
        font-size: 18px !important;
        pointer-events: none !important;
    }

    .saas-page-title, #content > h1, #content-main > h1 {
        font-size: 20px !important;
        font-weight: 700 !important;
        padding: 0 20px !important;
        margin: 0 0 20px 0 !important;
        color: #f8fafc !important;
        line-height: 1.3 !important;
    }

    /* 4. Bottom Navigation */
    .saas-sidebar {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        top: auto !important;
        width: 100% !important;
        height: auto !important;
        background-color: rgba(15, 23, 42, 0.85) !important; /* slate-900 transparent */
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-top: 1px solid #1e293b !important; /* slate-800 */
        border-radius: 0 !important;
        padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0px)) 16px !important;
        margin: 0 !important;
        z-index: 9999 !important;
        display: flex !important;
        flex-direction: row !important;
        justify-content: space-around !important;
        align-items: center !important;
    }

    .saas-sidebar > div {
        display: flex !important;
        flex-direction: row !important;
        width: 100% !important;
        justify-content: space-between !important;
        align-items: center !important;
    }

    .sidebar-brand { display: none !important; }

    .sidebar-menu, .sidebar-footer {
        display: flex !important;
        flex-direction: row !important;
        justify-content: space-around !important;
        align-items: center !important;
        margin: 0 !important;
        padding: 0 !important;
        width: auto !important;
    }
    
    .sidebar-menu { flex: 1 !important; }

    .sidebar-item, .sidebar-btn-logout {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        flex: 1 !important;
        height: 50px !important;
        background: transparent !important;
        border: none !important;
        text-decoration: none !important;
        color: #64748b !important; /* slate-500 */
        padding: 0 !important;
        margin: 0 !important;
        transition: color 0.2s ease !important;
    }

    .sidebar-item i, .sidebar-btn-logout i {
        font-size: 22px !important;
        margin-bottom: 4px !important;
    }

    .sidebar-text {
        font-size: 10px !important;
        font-weight: 600 !important;
    }

    .sidebar-item.active {
        color: #38bdf8 !important; /* sky-400 */
    }

    .sidebar-btn-logout {
        color: #f43f5e !important; /* rose-500 */
    }

    /* 5. Dashboard Grid & Cards */
    .saas-grid {
        display: flex !important;
        flex-direction: column !important;
        gap: 16px !important;
        padding: 0 20px !important;
    }

    .saas-left-col, .saas-right-col {
        display: flex !important;
        flex-direction: column !important;
        gap: 16px !important;
        width: 100% !important;
    }

    .saas-widget, .saas-metric-card, .saas-db-card {
        background-color: #1e293b !important; /* slate-800 */
        border: 1px solid #334155 !important; /* slate-700 */
        border-radius: 16px !important;
        width: 100% !important;
    }

    .saas-widget-header {
        padding: 16px 20px !important;
        border-bottom: 1px solid #334155 !important;
    }

    .saas-widget-header h3 {
        font-size: 15px !important;
        font-weight: 600 !important;
        color: #f8fafc !important;
    }

    .saas-widget-body {
        padding: 20px !important;
    }

    /* Metrics (Side by Side) */
    .saas-metrics-row {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 12px !important;
        padding: 0 20px !important;
    }

    .saas-metric-card {
        padding: 16px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }

    .saas-metric-title {
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #94a3b8 !important;
    }

    .saas-metric-value {
        font-size: 24px !important;
        font-weight: 700 !important;
        margin: 6px 0 !important;
        color: #f8fafc !important;
    }

    .saas-metric-subtext {
        font-size: 12px !important;
        color: #64748b !important;
    }

    /* 6. Dashboard Tickets -> Minimal Cards */
    .saas-table {
        display: block !important;
        width: 100% !important;
    }
    .saas-table thead { display: none !important; }
    .saas-table tbody {
        display: flex !important;
        flex-direction: column !important;
        width: 100% !important;
    }
    .saas-table tbody tr {
        display: flex !important;
        flex-direction: column !important;
        padding: 16px 20px !important;
        border-bottom: 1px solid #334155 !important;
    }
    .saas-table tbody tr:last-child {
        border-bottom: none !important;
    }
    .saas-table td {
        display: block !important;
        width: 100% !important;
        padding: 0 !important;
        border: none !important;
    }
    .saas-user-cell { gap: 12px !important; }
    .saas-subject { font-size: 14px !important; color: #94a3b8 !important; margin-top: 6px !important; }
    .saas-table tbody tr td:nth-child(3) { display: none !important; }
    .saas-action-link {
        height: 36px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        margin-top: 12px !important;
        background-color: #38bdf8 !important; /* sky-400 */
        color: #0f172a !important; /* dark text */
        padding: 0 16px !important;
        width: fit-content !important;
    }

    /* 7. Object Tools (Add button) */
    .object-tools {
        display: flex !important;
        padding: 0 20px !important;
        margin: 0 0 16px 0 !important;
        list-style: none !important;
    }

    .object-tools li { width: 100% !important; }

    .object-tools a {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        background-color: #38bdf8 !important; /* sky-400 */
        color: #0f172a !important; /* slate-900 */
        text-decoration: none !important;
    }

    /* 8. Changelist Search */
    #changelist-search {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
        padding: 0 20px 16px 20px !important;
    }

    #changelist-search #searchbar {
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        padding: 0 16px 0 44px !important;
        font-size: 15px !important;
        background-color: #1e293b !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2364748b'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z'%3E%3C/path%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important;
        background-position: 14px center !important;
        background-size: 20px !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
    }

    #changelist-search input[type="submit"] {
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
    }

    /* 9. Changelist Filter (Horizontal Swipe) */
    #changelist-filter {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        overflow-x: auto !important;
        padding: 0 20px 16px 20px !important;
        -ms-overflow-style: none;
        scrollbar-width: none;
    }
    #changelist-filter::-webkit-scrollbar { display: none; }
    #changelist-filter h3 { display: none !important; }

    #changelist-filter ul {
        display: flex !important;
        flex-direction: row !important;
        gap: 8px !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    #changelist-filter li a {
        display: flex !important;
        align-items: center !important;
        padding: 0 16px !important;
        height: 36px !important;
        border-radius: 18px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #94a3b8 !important;
        white-space: nowrap !important;
    }

    #changelist-filter li.selected a {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
        border-color: #38bdf8 !important;
        font-weight: 600 !important;
    }

    /* 10. Actions Toolbar */
    .actions {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
        padding: 0 20px 16px 20px !important;
        background: transparent !important;
        border: none !important;
    }

    .actions select {
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        padding: 0 16px !important;
        font-size: 15px !important;
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
        appearance: none;
    }

    .actions button.button {
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        background-color: #f8fafc !important; /* white */
        color: #0f172a !important; /* black */
        border: none !important;
    }
    
    .actions > span { display: none !important; }

    /* 11. Changelist Main Table */
    #changelist .results {
        padding: 0 20px !important;
    }

    #changelist table {
        display: block !important;
        width: 100% !important;
        border: none !important;
    }

    #changelist table thead { display: none !important; }
    #changelist table tbody {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
        width: 100% !important;
    }

    #changelist table tbody tr {
        display: flex !important;
        flex-direction: column !important;
        background-color: #1e293b !important; /* slate-800 */
        border: 1px solid #334155 !important;
        border-radius: 16px !important;
        padding: 16px !important;
        position: relative !important;
    }

    #changelist table tbody tr.selected {
        background-color: rgba(56, 189, 248, 0.1) !important;
        border-color: rgba(56, 189, 248, 0.3) !important;
    }

    #changelist table tbody td.action-checkbox {
        position: absolute !important;
        top: 16px !important;
        right: 16px !important;
        display: block !important;
    }

    #changelist table tbody td.action-checkbox input {
        width: 20px !important;
        height: 20px !important;
        accent-color: #38bdf8 !important;
        margin: 0 !important;
        border-radius: 4px !important;
    }

    #changelist table tbody th {
        display: block !important;
        width: calc(100% - 32px) !important;
        padding: 0 0 8px 0 !important;
        margin-bottom: 8px !important;
        border-bottom: 1px solid #334155 !important;
        text-align: left !important;
    }

    #changelist table tbody th a {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #f8fafc !important;
        line-height: 1.4 !important;
        text-decoration: none !important;
    }

    #changelist table tbody td {
        display: block !important;
        width: 100% !important;
        padding: 4px 0 !important;
        font-size: 14px !important;
        color: #94a3b8 !important;
        border: none !important;
        text-align: left !important;
    }

    /* Paginator */
    .paginator {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
        justify-content: center !important;
        padding: 24px 20px !important;
        border: none !important;
        background: transparent !important;
    }

    .paginator a, .paginator span {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-width: 36px !important;
        height: 36px !important;
        padding: 0 10px !important;
        border-radius: 8px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        background-color: #1e293b !important;
        color: #94a3b8 !important;
        text-decoration: none !important;
        border: 1px solid #334155 !important;
    }

    .paginator .this-page {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
        border-color: #38bdf8 !important;
        font-weight: 600 !important;
    }

    /* 12. Add/Edit Forms */
    .form-row {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
        padding: 16px 20px !important;
        border-bottom: 1px solid #1e293b !important;
    }

    .form-row label {
        font-size: 14px !important;
        font-weight: 500 !important;
        color: #94a3b8 !important;
        margin: 0 !important;
        display: block !important;
        text-align: left !important;
    }

    .form-row input[type="text"],
    .form-row input[type="password"],
    .form-row input[type="email"],
    .form-row input[type="number"],
    .form-row input[type="url"],
    .form-row textarea,
    .form-row select,
    .vTextField,
    .vLargeTextField,
    .vUUIDField {
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        padding: 0 16px !important;
        font-size: 15px !important;
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
    }

    .form-row textarea {
        height: 120px !important;
        padding: 12px 16px !important;
        resize: none !important;
    }

    .form-row .checkbox-row {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 12px !important;
    }
    
    .form-row .checkbox-row input[type="checkbox"] {
        width: 20px !important;
        height: 20px !important;
        accent-color: #38bdf8 !important;
        margin: 0 !important;
    }

    /* Submit Row */
    .submit-row {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
        padding: 20px !important;
        margin: 20px !important;
        background-color: #1e293b !important;
        border-radius: 16px !important;
        border: 1px solid #334155 !important;
        position: static !important;
    }

    .submit-row input,
    .submit-row a {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        height: 48px !important;
        border-radius: 12px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        text-decoration: none !important;
        border: none !important;
    }

    .submit-row input[name="_save"] {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
    }

    .submit-row input[name="_addanother"],
    .submit-row input[name="_continue"] {
        background-color: transparent !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
    }

    .submit-row .deletelink-box {
        margin: 0 !important;
        width: 100% !important;
    }
    
    .submit-row a.deletelink {
        background-color: rgba(244, 63, 94, 0.1) !important;
        color: #f43f5e !important;
    }

    /* 13. Login Page */
    body.login {
        padding: 20px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-height: 100vh !important;
        min-height: 100dvh !important;
        background-color: #0f172a !important;
    }

    body.login #container {
        width: 100% !important;
        max-width: 400px !important;
    }

    body.login #content {
        padding: 32px 24px !important;
        border-radius: 20px !important;
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
    }

    body.login #content input[type="text"],
    body.login #content input[type="password"] {
        height: 52px !important;
        border-radius: 12px !important;
        font-size: 15px !important;
        padding: 0 16px !important;
        width: 100% !important;
        background-color: #0f172a !important;
        border: 1px solid #334155 !important;
    }

    body.login .submit-row {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 24px 0 0 0 !important;
    }

    body.login .submit-row input[type="submit"] {
        height: 52px !important;
        border-radius: 12px !important;
        font-size: 16px !important;
        background-color: #38bdf8 !important;
        color: #0f172a !important;
    }

    /* Hide redundant elements */
    .glowing-orb { display: none !important; }

    /* Messages */
    .messagelist {
        margin: 0 20px 16px 20px !important;
        border-radius: 12px !important;
    }
    .messagelist li {
        padding: 12px 16px !important;
        font-size: 14px !important;
        border-radius: 12px !important;
        margin-bottom: 8px !important;
    }
}
"""
    new_content = content[:start_idx] + new_media_query
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("CSS updated successfully.")
else:
    print("Could not find the media query block.")
