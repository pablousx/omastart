.pragma library

function sourceLabel(kind) {
    return {hyprland: "Hyprland", xdg: "XDG autostart", systemd: "User systemd"}[kind] || kind
}

function openingOrder(applications) {
    return applications.slice().sort(function(a, b) {
        if (!!a.enabled !== !!b.enabled) return a.enabled ? -1 : 1
        var first = a.name.toLowerCase()
        var second = b.name.toLowerCase()
        return first < second ? -1 : first > second ? 1 : a.id.localeCompare(b.id)
    }).map(function(app) { return app.id })
}

function ordered(applications, order) {
    var remaining = new Map()
    applications.forEach(function(app) { remaining.set(app.id, app) })
    var result = []
    order.forEach(function(id) {
        if (remaining.has(id)) {
            result.push(remaining.get(id))
            remaining.delete(id)
        }
    })
    // Newly discovered apps join the end without moving existing rows.
    remaining.forEach(function(app) { result.push(app) })
    return result
}

function filtered(applications, query, sourceFilter, statusFilter, showSystem) {
    var needle = String(query || "").trim().toLowerCase()
    var readOnlyView = statusFilter === "readonly"
    var matches = applications.filter(function(app) {
        return (readOnlyView ? locked(app) : !locked(app))
            && (readOnlyView || showSystem || !app.system)
            && (!needle || app.search.indexOf(needle) !== -1)
            && (sourceFilter === "all" || app.kinds.indexOf(sourceFilter) !== -1)
    })
    if (!readOnlyView) return matches
    return matches.filter(function(app) { return app.enabled })
        .concat(matches.filter(function(app) { return !app.enabled && app.status !== "Disabled" }))
        .concat(matches.filter(function(app) { return app.status === "Disabled" }))
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

function findSource(applications, id) {
    for (var i = 0; i < applications.length; i++) {
        for (var j = 0; j < applications[i].sources.length; j++) {
            if (applications[i].sources[j].id === id) return applications[i].sources[j]
        }
    }
    return null
}

function findApplication(applications, id) {
    return applications.find(function(app) { return app.id === id }) || null
}

function findRemoval(inventory, id) {
    return (inventory.removed || []).find(function(app) { return app.id === id }) || null
}

function preferredSource(app) {
    return (app.sources || []).find(function(source) { return source.id === app.preferredSource }) || null
}

function locked(app) {
    return app.sources.length > 0 && app.sources.every(function(s) { return !!s.readOnly })
}
