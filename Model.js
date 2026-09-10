.pragma library

function sourceLabel(kind) {
    return {hyprland: "Hyprland", xdg: "XDG autostart", systemd: "User systemd"}[kind] || kind
}

function filtered(applications, query, sourceFilter, statusFilter, showSystem) {
    var needle = String(query || "").trim().toLowerCase()
    return applications.filter(function(app) {
        return (showSystem || !app.system)
            && (!needle || app.search.indexOf(needle) !== -1)
            && (sourceFilter === "all" || app.kinds.indexOf(sourceFilter) !== -1)
            && (statusFilter === "all" || (statusFilter === "enabled" ? app.enabled : !app.enabled))
    })
}

function catalogFiltered(catalog, query) {
    var needle = String(query || "").trim().toLowerCase()
    return catalog.filter(function(app) {
        return !needle || (app.name + " " + app.command).toLowerCase().indexOf(needle) !== -1
    })
}

function subtitle(app) {
    var kinds = app.activeKinds.length ? app.activeKinds : app.kinds
    var value = kinds.map(sourceLabel).join(" · ")
    if (app.duplicate) value += " · Multiple startup sources"
    else if (app.sources.length > 1) value += " · " + app.sources.length + " sources"
    return value
}

function sourceState(item) {
    if (item.enabled === null) return "Unknown"
    if (!item.enabled) return item.masked ? "Disabled for you" : "Disabled"
    if (item.eligible === false) return "Not applicable"
    if (item.eligible === null) return "Conditional"
    return item.globalEnabled ? "Enabled globally" : "Enabled"
}
