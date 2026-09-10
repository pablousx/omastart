import QtQuick
import Quickshell
import QtTest
import "plugin" as Plugin
import "plugin/Model.js" as Model

ShellRoot {
    id: test
    Component.onCompleted: { panel.refresh(); panel.expandedId = "vicinae" }
    property int assertions: 0
    function check(condition, explanation) {
        assertions++
        if (!condition) throw new Error(explanation)
    }
    function find(item, name) {
        if (item.objectName === name) return item
        var children = item.children || []
        for (var i = 0; i < children.length; i++) {
            var result = find(children[i], name)
            if (result) return result
        }
        return null
    }
    function checkRefreshFocus() {
        try {
            var list = test.find(panel, "applicationList")
            list.forceLayout()
            var toggle = panel.findControl(list, "detail-xdg:vicinae.desktop", false)
            test.check(toggle !== null, "Expanded startup control must be reachable")
            toggle.forceActiveFocus()
            var remembered = panel.rememberListFocus()
            test.check(remembered && remembered.id === "vicinae", "Refresh must remember the focused app")
            panel.pendingRequest = {action:"scan"}
            var refreshed = JSON.parse(JSON.stringify(panel.inventory))
            refreshed.ok = true
            panel.finish(JSON.stringify(refreshed), "", 0)
            Qt.callLater(function() {
                try {
                    var restored = panel.findControl(list, "detail-xdg:vicinae.desktop", false)
                    test.check(restored && restored.activeFocus, "Background refresh must restore the exact startup control's keyboard focus")
                    console.log("OMASTART_QML_PASS " + test.assertions + " assertions")
                    Qt.quit()
                } catch (error) { console.error("OMASTART_QML_FAIL " + error); Qt.quit() }
            })
        } catch (error) { console.error("OMASTART_QML_FAIL " + error); Qt.quit() }
    }
    property var fixture: ({
        applications: [
            {id:"vicinae", name:"Vicinae", icon:"", enabled:true, status:"Enabled", system:false,
             kinds:["xdg","systemd"], activeKinds:["xdg"], duplicate:false, search:"vicinae server xdg systemd",
             sources:[{id:"xdg:vicinae.desktop", kind:"xdg", name:"Vicinae", enabled:true, eligible:true, readOnly:"", command:"vicinae server", path:"/fixture/autostart/vicinae.desktop", running:"active", revision:"fixture", generatedUnits:["app-vicinae@autostart.service"]},
                      {id:"systemd:vicinae.service", kind:"systemd", name:"Vicinae", enabled:false, eligible:true, readOnly:"", command:"vicinae server", path:"/fixture/vicinae.service", running:"inactive", revision:"fixture"}]},
            {id:"synergy", name:"Synergy", icon:"", enabled:true, status:"Enabled", system:false,
             kinds:["systemd"], activeKinds:["systemd"], duplicate:false, search:"synergy systemd",
             sources:[{id:"systemd:synergy.service", kind:"systemd", name:"Synergy", enabled:true, eligible:true, readOnly:"", command:"synergy-service", path:"/fixture/synergy.service", running:"active", revision:"fixture", globalEnabled:true}]},
            {id:"pipewire", name:"PipeWire", icon:"", enabled:true, status:"Enabled", system:true,
             kinds:["systemd"], activeKinds:["systemd"], duplicate:false, search:"pipewire systemd",
             sources:[{id:"systemd:pipewire.service", kind:"systemd", name:"PipeWire", enabled:true, eligible:true, readOnly:"Protected infrastructure", command:"pipewire", path:"/fixture/pipewire.service", running:"active", revision:"fixture"}]}
        ], catalog:[{id:"sample.desktop", name:"Sample", command:"sample", icon:"", exists:false, revision:"fixture"}],
        warnings:[], counts:{applications:2, enabled:2, system:1}
    })

    FloatingWindow {
      visible: true
      implicitWidth: 640
      implicitHeight: 800
      Item {
        id: anchor
        TestEvent { id: events }
        Plugin.BarWidget { id: widget; x: 580 }
        width: 24
        height: 24
        Plugin.Panel {
            id: panel
            anchorItem: anchor
            fixtureData: test.fixture
        }
        Plugin.ApplicationRow {
            id: row
            width: 540
            entry: test.fixture.applications[0]
            manager: panel
        }
      }
    }

    Timer {
        interval: 300
        running: true
        onTriggered: {
            try {
                panel.refresh()
                test.check(widget.ownPanel() !== null, "Bar widget must load its panel")
                widget.ownPanel().fixtureData = test.fixture
                test.check(panel.loaded, "Fixture panel did not load")
                test.check(!panel.busy, "Fixture tried to launch a backend")
                test.check(panel.applications.length === 2, "Infrastructure must be hidden by default")
                panel.setSearch("VICINAE")
                test.check(panel.applications.length === 1, "Search must be case insensitive")
                test.check(panel.inspect().rows[0].name === "Vicinae", "Inspection must reflect displayed rows")
                test.check(Model.subtitle(panel.applications[0]) === "XDG autostart · 2 sources", "Inactive alternatives must not obscure enabled source")
                test.check(row.implicitHeight > 150, "Expanded details did not get layout space")
                panel.expandedId = ""
                row.activate()
                test.check(panel.expandedId === "vicinae", "Row activation must expand sources, not toggle startup")
                test.check(row.expanded, "Expanded row did not follow selection")
                panel.sourceFilter = "hyprland"
                test.check(panel.applications.length === 0, "Source filter failed")
                panel.sourceFilter = "all"
                panel.setSearch("")
                panel.statusFilter = "disabled"
                test.check(panel.applications.length === 0, "Status filter failed")
                panel.statusFilter = "all"
                panel.showSystem = true
                test.check(panel.applications.length === 3, "System items cannot be inspected")
                test.check(Model.sourceState(test.fixture.applications[1].sources[0]) === "Enabled globally", "Global enablement label failed")
                panel.adding = true
                panel.setSearch("sample")
                test.check(panel.choices.length === 1, "Application picker filter failed")
                panel.addApplication(panel.choices[0])
                test.check(!panel.busy, "Fixture mutations must never run a backend")
                panel.adding = false
                panel.setSearch("")
                var search = test.find(panel, "searchField")
                test.check(search !== null, "Search field not found")
                search.forceActiveFocus()
                test.check(events.keyClick(Qt.Key_V, Qt.NoModifier, 0), "Could not send fixture keyboard input")
                test.check(panel.inspect().query === "v", "Typing did not reach search")
                test.check(events.keyClick(Qt.Key_Down, Qt.NoModifier, 0), "Could not navigate to list")
                test.check(!search.activeFocus, "Down did not transfer keyboard focus to list")
                search.forceActiveFocus()
                events.keyClick(Qt.Key_Escape, Qt.NoModifier, 0)
                test.check(panel.inspect().query === "", "Escape must clear search first")
                panel.finish('{"ok":false,"error":"Simulated failure"}', "", 1)
                test.check(panel.error === "Simulated failure", "Backend errors must be visible")
                test.check(panel.inventory.applications[0].enabled, "A failed request must preserve displayed startup state")
                // Common navigation must work without remembering a hidden cycle.
                panel.setSearch("")
                test.find(panel, "status-disabled").clicked()
                test.check(panel.statusFilter === "disabled", "Disabled tab must select directly")
                test.find(panel, "status-enabled").clicked()
                test.check(panel.statusFilter === "enabled", "Enabled tab must select directly")
                test.find(panel, "status-all").clicked()
                test.find(panel, "filtersButton").clicked()
                test.check(panel.filtersOpen, "Source filters must be discoverable")
                panel.sourceFilter = "xdg"
                panel.showSystem = true
                panel.resetFilters()
                test.check(panel.sourceFilter === "all" && panel.statusFilter === "all" && !panel.showSystem, "Reset must clear every hidden filter")
                panel.setSearch("not installed")
                test.find(panel, "clearSearchButton").clicked()
                test.check(panel.inspect().query === "" && search.activeFocus, "Clear search must restore typing focus")
                search.forceActiveFocus()
                events.keyClick(Qt.Key_Down, Qt.NoModifier, 0)
                events.keyClick(Qt.Key_Up, Qt.NoModifier, 0)
                test.check(search.activeFocus, "Up from the first row must return to search")
                events.keyClick(Qt.Key_Down, Qt.NoModifier, 0)
                events.keyClick(Qt.Key_F, Qt.ControlModifier, 0)
                test.check(search.activeFocus, "Ctrl+F must reach search from the list")
                panel.expandedId = "vicinae"
                panel.handleEscape()
                test.check(panel.expandedId === "", "Escape must collapse details before dismissing")
                panel.filtersOpen = true
                panel.handleEscape()
                test.check(!panel.filtersOpen, "Escape must collapse filters before dismissing")
                panel.setSearch("Vicinae")
                panel.enterPicker()
                test.check(panel.adding && panel.inspect().query === "", "Picker must start with its own empty search")
                panel.setSearch("sample")
                panel.handleEscape()
                test.check(panel.adding && panel.inspect().query === "", "Picker Escape must clear search first")
                panel.handleEscape()
                test.check(!panel.adding && panel.inspect().query === "Vicinae", "Back from picker must restore startup search")
                panel.enterPicker()
                panel.viewApplication({id:"vicinae.desktop", identity:"vicinae"})
                test.check(!panel.adding && panel.expandedId === "vicinae" && panel.inspect().query === "Vicinae", "Manage existing picker entry must open its startup settings")
                row.technical = true
                panel.expandedId = ""
                test.check(!row.technical, "Technical details must reset when collapsed")
                test.check(Model.locked(test.fixture.applications[2]), "Infrastructure must explain a read-only state")
                test.check(!Model.locked(test.fixture.applications[0]), "Editable alternatives must stay available")

                // Exercise real response handling with isolated snapshots; never run a backend.
                var saved = JSON.parse(JSON.stringify(test.fixture))
                saved.ok = true
                saved.applications[0].sources[0].enabled = false
                saved.applications[0].sources[0].canUndo = true
                saved.applications[0].sources[0].revision = "saved-revision"
                saved.applications[0].enabled = false
                saved.applications[0].status = "Disabled"
                panel.pendingRequest = {action:"toggle", id:"xdg:vicinae.desktop", name:"Vicinae", enabled:false}
                panel.pendingId = "xdg:vicinae.desktop"
                panel.busy = true
                test.check(row.pending, "Only the changed row should show Saving")
                panel.finish(JSON.stringify(saved), "", 0)
                test.check(!panel.busy && !row.pending, "Successful saves must end row progress")
                test.check(panel.message === "Vicinae won't start at login.", "Success must name the app and saved outcome")
                test.check(panel.canUndoMessage, "Successful reversible change must offer immediate Undo")
                var changedElsewhere = JSON.parse(JSON.stringify(saved))
                changedElsewhere.applications[0].sources[0].revision = "external-revision"
                panel.pendingRequest = {action:"scan"}
                panel.finish(JSON.stringify(changedElsewhere), "", 0)
                test.check(!panel.canUndoMessage, "Toast Undo must not undo a later external change")
                test.check(panel.message !== "", "Background refresh must preserve save feedback")
                saved.applications[0].sources[1].enabled = true
                saved.applications[0].enabled = true
                panel.pendingRequest = {action:"toggle", id:"xdg:vicinae.desktop", name:"Vicinae", enabled:false}
                panel.finish(JSON.stringify(saved), "", 0)
                test.check(panel.message.indexOf("another enabled startup source") !== -1, "Disabling one source must not claim the whole app is disabled")
                panel.pendingRequest = {action:"undo", id:"xdg:vicinae.desktop"}
                panel.finish(JSON.stringify(saved), "", 0)
                test.check(panel.message === "Previous startup setting restored." && !panel.canUndoMessage, "Undo feedback must confirm restoration without an ambiguous redo")
                panel.error = "Save failed; review settings"
                panel.pendingRequest = {action:"scan"}
                panel.finish(JSON.stringify(saved), "", 0)
                test.check(panel.error !== "", "Automatic refresh must not erase an unacknowledged failure")
                panel.refresh(true)
                test.check(panel.error === "", "Manual refresh must acknowledge the failure")
                panel.dismissMessage()
                test.check(!panel.message && !panel.canUndoMessage, "Dismissal must clear the toast action too")
                var unknown = JSON.parse(JSON.stringify(test.fixture.applications[0]))
                unknown.enabled = false
                unknown.status = "Unknown"
                test.check(Model.filtered([unknown], "", "all", "disabled", false).length === 0, "Unknown state must not be presented as Disabled")
                panel.resetFilters()
                panel.setSearch("Vicinae")
                panel.expandedId = ""
                search.forceActiveFocus()
                events.keyClick(Qt.Key_Return, Qt.NoModifier, 0)
                test.check(panel.expandedId === "vicinae", "Enter from search must open the matching app")
                Qt.callLater(test.checkRefreshFocus)
            } catch (error) {
                console.error("OMASTART_QML_FAIL " + error)
                Qt.quit()
            }
        }
    }
}
