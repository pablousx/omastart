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
                    test.startLayoutCheck()
                } catch (error) { console.error("OMASTART_QML_FAIL " + error); Qt.quit() }
            })
        } catch (error) { console.error("OMASTART_QML_FAIL " + error); Qt.quit() }
    }
    function checkSessionOrder() {
        var snapshot = JSON.parse(JSON.stringify(test.fixture))
        snapshot.ok = true
        snapshot.applications[0].name = "Zulu"
        snapshot.applications[1].name = "Alpha"
        snapshot.applications[1].enabled = false
        snapshot.applications[1].status = "Disabled"
        snapshot.applications[1].sources[0].enabled = false
        panel.close()
        panel.resetFilters()
        panel.fixtureData = snapshot
        panel.open()
        test.check(panel.applications.map(function(app) { return app.id }).join() === "vicinae,synergy", "Opening must place enabled apps ahead of alphabetically earlier disabled apps")

        snapshot.applications[0].enabled = false
        snapshot.applications[0].startupEnabled = false
        snapshot.applications[0].status = "Disabled"
        snapshot.applications[0].sources[0].enabled = false
        panel.pendingRequest = {action:"toggleApplication", id:"vicinae", name:"Zulu", enabled:false}
        panel.finish(JSON.stringify(snapshot), "", 0)
        test.check(panel.applications[0].id === "vicinae", "Disabling an app must not move its row")

        snapshot.applications[1].enabled = true
        snapshot.applications[1].status = "Enabled"
        snapshot.applications[1].sources[0].enabled = true
        panel.pendingRequest = {action:"toggle", id:"systemd:synergy.service", name:"Alpha", enabled:true}
        panel.finish(JSON.stringify(snapshot), "", 0)
        test.check(panel.applications.map(function(app) { return app.id }).join() === "vicinae,synergy", "Enabling a source must not move its application ahead of another row")

        snapshot.applications.reverse()
        panel.pendingRequest = {action:"scan"}
        panel.finish(JSON.stringify(snapshot), "", 0)
        panel.fixtureData = snapshot
        panel.refresh(true)
        test.check(panel.applications.map(function(app) { return app.id }).join() === "vicinae,synergy", "Background and manual refreshes must retain the opening order")
        panel.setSearch("synergy")
        panel.setSearch("")
        panel.statusFilter = "readonly"
        panel.statusFilter = "all"
        panel.enterPicker()
        panel.leavePicker()
        test.check(panel.applications[0].id === "vicinae", "Search, tab changes, and returning from the picker must not reorder applications")

        var added = JSON.parse(JSON.stringify(test.fixture.applications[1]))
        added.id = "new-app"
        added.name = "Aardvark"
        snapshot.applications.unshift(added)
        panel.pendingRequest = {action:"scan"}
        panel.finish(JSON.stringify(snapshot), "", 0)
        test.check(panel.applications.map(function(app) { return app.id }).join() === "vicinae,synergy,new-app", "Newly discovered applications must append without shifting existing rows")

        panel.fixtureData = snapshot
        panel.close()
        panel.open()
        test.check(panel.applications.map(function(app) { return app.id }).join() === "new-app,synergy,vicinae", "Reopening must sort by current enabled state and alphabetically within each group")
        snapshot.applications = snapshot.applications.filter(function(app) { return app.id !== "synergy" })
        panel.pendingRequest = {action:"scan"}
        panel.finish(JSON.stringify(snapshot), "", 0)
        test.check(panel.applications.map(function(app) { return app.id }).join() === "new-app,vicinae", "Removed applications must disappear without disturbing remaining order")

        panel.close()
        panel.fixtureData = test.fixture
        panel.open()
        panel.close()
        panel.dismissMessage()
    }
    property int layoutStep: 0
    property var layoutSnapshot: null
    property var layoutBaseline: null
    function startLayoutCheck() {
        layoutSnapshot = JSON.parse(JSON.stringify(test.fixture))
        layoutSnapshot.ok = true
        for (var i = 0; i < 10; i++) {
            var entry = JSON.parse(JSON.stringify(test.fixture.applications[1]))
            entry.id = "layout-" + i
            entry.name = "Layout app " + i
            entry.sources[0].id = "systemd:layout-" + i + ".service"
            layoutSnapshot.applications.push(entry)
        }
        layoutSnapshot.applications[0].name = "Zulu application"
        panel.close()
        panel.resetFilters()
        panel.expandedId = ""
        panel.dismissMessage()
        panel.fixtureData = layoutSnapshot
        panel.open()
        // Allow actual frames between states: synchronous property checks do
        // not catch ColumnLayout resizing or end-of-list scroll clamping.
        layoutTimer.start()
    }
    function layoutGeometry() {
        var list = test.find(panel, "applicationList")
        list.forceLayout()
        var index = panel.applications.findIndex(function(app) { return app.id === "vicinae" })
        var entry = list.itemAtIndex(index)
        var toggle = test.find(entry, "startupToggle")
        var position = toggle.mapToItem(panel, 0, 0)
        return {listY:list.y, listHeight:list.height, scroll:list.contentY,
            rowHeight:entry.height, titleWidth:test.find(entry, "applicationTitle").width,
            toggleX:position.x, toggleY:position.y, footerHeight:test.find(panel, "feedback").height}
    }
    Timer {
        id: layoutTimer
        interval: 60
        repeat: true
        onTriggered: {
            try {
                if (test.layoutStep === 0) {
                    var list = test.find(panel, "applicationList")
                    list.forceLayout()
                    list.positionViewAtEnd()
                } else if (test.layoutStep === 1) {
                    test.layoutBaseline = test.layoutGeometry()
                    test.check(test.layoutBaseline.scroll > 0, "Layout regression must exercise a scrolled list")
                    panel.pendingRequest = {action:"toggleApplication", id:"vicinae", name:"Zulu application", enabled:false}
                    panel.pendingId = "vicinae"
                    panel.busy = true
                } else {
                    test.check(JSON.stringify(test.layoutGeometry()) === JSON.stringify(test.layoutBaseline),
                        "Toggle feedback must preserve viewport, scroll, title width, row height, and switch position at step " + test.layoutStep)
                    if (test.layoutStep === 2 || test.layoutStep === 4) {
                        var enabled = test.layoutStep === 4
                        test.layoutSnapshot.applications[0].enabled = enabled
                        test.layoutSnapshot.applications[0].startupEnabled = enabled
                        test.layoutSnapshot.applications[0].status = enabled ? "Enabled" : "Disabled"
                        test.layoutSnapshot.applications[0].sources[0].enabled = enabled
                        test.layoutSnapshot.applications[0].canUndo = true
                        test.layoutSnapshot.applications[0].revision = enabled ? "enabled-layout" : "disabled-layout"
                        panel.finish(JSON.stringify(test.layoutSnapshot), "", 0)
                    } else if (test.layoutStep === 3) {
                        panel.pendingRequest = {action:"toggleApplication", id:"vicinae", name:"Zulu application", enabled:true}
                        panel.pendingId = "vicinae"
                        panel.busy = true
                    } else if (test.layoutStep === 5) {
                        panel.message = "A longer application name will start at login via the selected startup method. Running applications stay open."
                    } else if (test.layoutStep === 6) {
                        panel.dismissMessage()
                    } else if (test.layoutStep === 7) {
                        layoutTimer.stop()
                        console.log("OMASTART_QML_PASS " + test.assertions + " assertions")
                        Qt.quit()
                    }
                }
                test.layoutStep++
            } catch (error) {
                layoutTimer.stop()
                console.error("OMASTART_QML_FAIL " + error)
                Qt.quit()
            }
        }
    }
    property var fixture: ({
        applications: [
            {id:"vicinae", name:"Vicinae", icon:"", enabled:true, status:"Enabled", system:false,
             startupEnabled:true, toggleReadOnly:"", preferredSource:"xdg:vicinae.desktop", revision:"application-fixture", canUndo:false,
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

    QtObject {
        id: fakeManager
        property bool busy: false
        property string pendingId: ""
        property string expandedId: ""
        property string lastApplication: ""
        property string lastSource: ""
        function changeApplication(app) { lastApplication = app.id }
        function change(source) { lastSource = source.id }
    }

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
                test.check(panel.statusFilter === "all" && panel.applications.length === 2, "Legacy status filters must resolve to Applications")
                panel.statusFilter = "all"
                panel.showSystem = true
                test.check(panel.applications.length === 2, "Read-only system items must stay out of Applications")
                panel.showSystem = false
                test.find(panel, "status-readonly").clicked()
                test.check(panel.readOnlyView && panel.applications.length === 1 && panel.applications[0].id === "pipewire", "Read-only tab must include protected system items without an extra filter")
                panel.statusFilter = "all"
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
                test.check(test.find(panel, "status-disabled") === null && test.find(panel, "status-enabled") === null, "Enabled and Disabled must not have separate tabs")
                test.check(test.find(panel, "status-all").text === "Applications", "Merged tab must be named Applications")
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

                var readOnlyOff = JSON.parse(JSON.stringify(test.fixture.applications[2]))
                readOnlyOff.id = "readonly-off"
                readOnlyOff.name = "A disabled item"
                readOnlyOff.enabled = false
                readOnlyOff.status = "Disabled"
                readOnlyOff.sources[0].enabled = false
                var mixedItems = [readOnlyOff, test.fixture.applications[0], test.fixture.applications[2], test.fixture.applications[1]]
                var readOnlyItems = Model.filtered(mixedItems, "", "all", "readonly", false)
                test.check(readOnlyItems.length === 2 && readOnlyItems[0].id === "pipewire" && readOnlyItems[1].id === "readonly-off", "Read-only enabled items must precede disabled items regardless of name")
                test.check(Model.filtered(mixedItems, "", "all", "all", true).every(function(app) { return !Model.locked(app) }), "Applications must exclude both enabled and disabled read-only items")
                var editableOff = JSON.parse(JSON.stringify(test.fixture.applications[1]))
                editableOff.id = "editable-off"
                editableOff.enabled = false
                editableOff.status = "Disabled"
                editableOff.sources[0].enabled = false
                mixedItems.push(editableOff)
                var editableItems = Model.filtered(mixedItems, "", "all", "all", false)
                test.check(editableItems.length === 3 && editableItems.some(function(app) { return app.enabled }) && editableItems.some(function(app) { return app.status === "Disabled" }), "Applications must show enabled and disabled editable items together")
                test.check(editableItems[0].id === "vicinae" && editableItems[2].id === "editable-off", "Merged tab must preserve application ordering")
                test.check(Model.filtered(mixedItems, "vicinae", "all", "readonly", false).length === 0, "Read-only search must not leak editable apps")
                test.check(Model.filtered(mixedItems, "", "xdg", "readonly", false).length === 0, "Source filters must still apply to the read-only tab")
                panel.viewApplication({id:"pipewire.desktop", identity:"pipewire"})
                test.check(panel.readOnlyView && panel.applications.length === 1 && panel.expandedId === "pipewire", "Manage must route read-only apps into their own tab")
                panel.resetFilters()

                row.manager = fakeManager
                var appToggle = test.find(row, "startupToggle")
                test.check(appToggle.visible && appToggle.checked, "Multi-method apps must expose a checked summary toggle")
                test.check(appToggle.applicationItem.id === "vicinae", "Summary toggle must target the whole application")
                appToggle.forceActiveFocus()
                events.keyClick(Qt.Key_Space, Qt.NoModifier, 0)
                test.check(fakeManager.lastApplication === "vicinae" && !fakeManager.lastSource, "Space must toggle the app, not its first source")
                fakeManager.lastApplication = ""
                fakeManager.busy = true
                appToggle.activate()
                test.check(!fakeManager.lastApplication, "An in-flight save must block another app toggle")
                fakeManager.busy = false
                var blockedApp = JSON.parse(JSON.stringify(test.fixture.applications[0]))
                blockedApp.toggleReadOnly = "An enabled method is read-only."
                row.entry = blockedApp
                appToggle.activate()
                test.check(!appToggle.interactive && !fakeManager.lastApplication, "A protected active method must block the summary toggle")
                test.check(appToggle.description === blockedApp.toggleReadOnly, "Disabled app toggles must explain the blocked method")
                blockedApp = JSON.parse(JSON.stringify(test.fixture.applications[0]))
                blockedApp.startupEnabled = false
                row.entry = blockedApp
                test.check(!appToggle.checked && appToggle.description.indexOf("XDG autostart") !== -1, "Disabled app toggle must disclose the chosen startup method")
                row.entry = test.fixture.applications[0]
                row.manager = panel

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

                var groupSaved = JSON.parse(JSON.stringify(test.fixture))
                groupSaved.ok = true
                groupSaved.applications[0].enabled = false
                groupSaved.applications[0].startupEnabled = false
                groupSaved.applications[0].sources[0].enabled = false
                groupSaved.applications[0].revision = "group-saved"
                groupSaved.applications[0].canUndo = true
                panel.pendingRequest = {action:"toggleApplication", id:"vicinae", name:"Vicinae", enabled:false}
                panel.pendingId = "vicinae"
                panel.busy = true
                test.check(row.pending, "Application saves must show progress on their row")
                panel.finish(JSON.stringify(groupSaved), "", 0)
                test.check(panel.message === "Vicinae won't start at login." && panel.canUndoMessage && panel.undoApplication, "Group save must offer an application-wide Undo")
                groupSaved.applications[0].revision = "external-group-edit"
                panel.pendingRequest = {action:"scan"}
                panel.finish(JSON.stringify(groupSaved), "", 0)
                test.check(!panel.canUndoMessage, "External changes must invalidate application-wide toast Undo")
                panel.pendingRequest = {action:"toggleApplication", id:"vicinae", name:"Vicinae", enabled:true}
                groupSaved.applications[0].enabled = true
                groupSaved.applications[0].startupEnabled = true
                panel.finish(JSON.stringify(groupSaved), "", 0)
                test.check(panel.message === "Vicinae will start at login via XDG autostart.", "Enable feedback must identify the selected method")
                panel.pendingRequest = {action:"undoApplication", id:"vicinae"}
                panel.finish(JSON.stringify(groupSaved), "", 0)
                test.check(panel.message === "Previous startup setting restored." && !panel.canUndoMessage, "Group undo must acknowledge restoration")
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
                test.check(Model.filtered([unknown], "", "all", "all", false)[0].status === "Unknown", "Merged tab must preserve unknown states without relabeling them Disabled")
                test.checkSessionOrder()
                var addedSnapshot = JSON.parse(JSON.stringify(test.fixture))
                addedSnapshot.ok = true
                var newApp = JSON.parse(JSON.stringify(test.fixture.applications[1]))
                newApp.id = "sample"
                newApp.name = "Sample"
                newApp.sources[0].id = "xdg:sample.desktop"
                newApp.sources[0].kind = "xdg"
                addedSnapshot.applications.push(newApp)
                panel.setSearch("Vicinae")
                panel.enterPicker()
                panel.pendingRequest = {action:"add", id:"sample.desktop", name:"Sample"}
                panel.finish(JSON.stringify(addedSnapshot), "", 0)
                panel.leavePicker()
                test.check(panel.applications[0].id === "sample" && panel.inspect().query === "", "Added apps must appear first when returning from the picker, even after a previous search")
                newApp.enabled = false
                newApp.status = "Disabled"
                newApp.canRemove = true
                newApp.sources[0].enabled = false
                panel.pendingRequest = {action:"toggle", id:"xdg:sample.desktop", enabled:false}
                panel.finish(JSON.stringify(addedSnapshot), "", 0)
                test.check(panel.applications[0].id === "sample", "Disabling the added item must keep it at the top")
                row.entry = newApp
                panel.expandedId = newApp.id
                test.check(test.find(row, "removeApplication").visible, "Disabled items must expose Remove in their details")
                addedSnapshot.applications.pop()
                addedSnapshot.removed = [{id:"sample", name:"Sample", revision:"removed", canUndo:true}]
                panel.pendingRequest = {action:"remove", id:"sample", name:"Sample"}
                panel.finish(JSON.stringify(addedSnapshot), "", 0)
                test.check(panel.undoRemoval && panel.canUndoMessage && !panel.expandedId, "Remove must offer Undo and close the removed details")
                test.check(!panel.applications.some(function(app) { return app.id === "sample" }), "Only explicit Remove should take the disabled item out of the list")
                row.entry = test.fixture.applications[0]
                test.check(!test.find(row, "removeApplication").visible, "Enabled items must not expose Remove")
                panel.fixtureData = test.fixture
                panel.refresh()
                panel.dismissMessage()
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
