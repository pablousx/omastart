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
                console.log("OMASTART_QML_PASS " + test.assertions + " assertions")
                Qt.quit()
            } catch (error) {
                console.error("OMASTART_QML_FAIL " + error)
                Qt.quit()
            }
        }
    }
}
