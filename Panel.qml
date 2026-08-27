import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.skymebr.usbguard"
  ipcTarget: "io.github.skymebr.usbguard"
  manageIpc: false

  readonly property string backendScript: Quickshell.env("HOME") + "/.config/omarchy/plugins/io.github.skymebr.usbguard/backend.py"

  property bool daemonActive: false
  property bool isInstalled: true
  property bool needsSetup: false
  property int blockedCount: 0
  property int badUsbCount: 0
  property int visibleCount: 0
  property var devices: []
  property var rules: []

  property string currentTab: "devices" // "devices" | "rules"

  readonly property bool hideHubs: setting("hideHubs", true) === true
  readonly property bool showBlockedBadge: setting("showBlockedBadge", true) === true

  readonly property var visibleDevices: devices.filter(function(d) {
    return !root.hideHubs || !d.is_hub
  })

  readonly property var blockedDevices: visibleDevices.filter(function(d) {
    return d.is_blocked
  })

  readonly property bool hasBlocked: blockedCount > 0
  readonly property bool hasBadUsb: badUsbCount > 0

  readonly property string barIcon: {
    if (!daemonActive) return "󰅖"
    if (hasBadUsb) return "󰕤"
    if (hasBlocked) return "󰌾"
    return "󰕓"
  }

  readonly property color barIconColor: {
    if (!daemonActive) return Color.muted
    if (hasBadUsb || hasBlocked) return Color.urgent
    return bar ? bar.barForeground : Color.foreground
  }

  function refresh() {
    if (!queryProc.running) {
      queryProc.running = true
    }
  }

  function allowDevice(devId, permanent) {
    if (!devId) return
    var args = ["python3", backendScript, "--allow", String(devId)]
    if (permanent) args.push("--permanent")
    runAction(args)
  }

  function blockDevice(devId) {
    if (!devId) return
    runAction(["python3", backendScript, "--block", String(devId)])
  }

  function rejectDevice(devId) {
    if (!devId) return
    runAction(["python3", backendScript, "--reject", String(devId)])
  }

  function removeRule(ruleId) {
    if (!ruleId) return
    runAction(["python3", backendScript, "--remove-rule", String(ruleId)])
  }

  function runAction(cmd) {
    actionProc.command = cmd
    actionProc.running = true
  }

  Component.onCompleted: refresh()

  Process {
    id: queryProc
    command: ["python3", root.backendScript, "--status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(text || "{}")
          root.daemonActive = data.daemon_active === true
          root.isInstalled = data.installed !== false
          root.needsSetup = data.needs_setup === true
          root.devices = data.devices || []
          root.rules = data.rules || []
          root.blockedCount = data.blocked_count || 0
          root.badUsbCount = data.badusb_count || 0
          root.visibleCount = data.visible_count || 0
        } catch (e) {}
      }
    }
  }

  Process {
    id: actionProc
    onExited: function(exitCode) {
      root.refresh()
    }
  }

  Timer {
    id: autoRefreshTimer
    interval: root.opened ? 2500 : 8000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  // ------------------------------------------------------------- Bar Button
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.hasBlocked && root.showBlockedBadge && !vertical
      ? root.barIcon + " " + root.blockedCount
      : root.barIcon
    slotSize: Style.bar.iconSlot * (root.hasBlocked && root.showBlockedBadge && !vertical ? 1.7 : 1)
    tooltipText: root.daemonActive
      ? (root.hasBlocked
          ? root.blockedCount + " USB device(s) blocked!"
          : "USBGuard: Protected (" + root.visibleCount + " devices)")
      : "USBGuard: Service Inactive"
    onPressed: function(b) {
      if (b === Qt.RightButton) root.refresh()
      else root.toggle()
    }
  }

  // ------------------------------------------------------------- Popup Panel
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(430))
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: mainColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Style.space(12)

        // 1. Hero Header
        PanelHero {
          title: "USBGuard"
          meta: root.needsSetup
            ? "INITIALIZATION REQUIRED"
            : (root.daemonActive
                ? (root.hasBadUsb ? "BADUSB THREAT DETECTED" : (root.hasBlocked ? root.blockedCount + " BLOCKED DEVICE(S)" : root.visibleCount + " CONNECTED"))
                : "SERVICE INACTIVE")
          iconComponent: Component {
            Text {
              text: root.hasBadUsb ? "󰕤" : (root.hasBlocked ? "󰌾" : (root.needsSetup ? "󰕤" : "󰕥"))
              color: root.hasBadUsb || root.hasBlocked || root.needsSetup ? Color.urgent : (root.daemonActive ? Color.accent : Color.muted)
              font.family: Style.font.family
              font.pixelSize: Style.font.display
            }
          }
          trailingControl: Component {
            Button {
              iconText: "󰑐"
              tooltipText: "Refresh"
              onClicked: root.refresh()
            }
          }
        }

        PanelSeparator {}

        // 2. Onboarding / Setup Banner (For fresh installs by other users)
        BorderSurface {
          width: parent.width
          visible: root.needsSetup || !root.daemonActive
          implicitHeight: setupCol.implicitHeight + Style.space(16)
          color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.08)
          borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)
          radius: Style.cornerRadius

          Column {
            id: setupCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Style.space(12)
            spacing: Style.space(10)

            Text {
              text: "Enable Hardware Protection"
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
            }

            Text {
              text: "Protect against BadUSB attacks and auto-allow your internal motherboard hardware (webcam, bluetooth, keyboard)."
              color: Color.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
              width: parent.width
            }

            Button {
              text: "🛡️ Run Security Setup"
              fontSize: Style.font.bodySmall
              selected: true
              onClicked: {
                Util.execDetached("omarchy-launch-terminal omarchy-setup-security-usbguard")
              }
            }
          }
        }

        // 3. Action Required Alert for Blocked / BadUSB Devices
        Column {
          width: parent.width
          spacing: Style.space(8)
          visible: root.hasBlocked && !root.needsSetup

          PanelSectionHeader {
            text: "ACTION REQUIRED"
            foreground: Color.urgent
          }

          Repeater {
            model: root.blockedDevices

            delegate: BorderSurface {
              width: parent.width
              implicitHeight: alertCol.implicitHeight + Style.space(16)
              color: Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.12)
              borderSpec: Border.controlSpec("urgent", Color.urgent, Color.urgent)
              radius: Style.cornerRadius

              Column {
                id: alertCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: Style.space(12)
                spacing: Style.space(10)

                Row {
                  width: parent.width
                  spacing: Style.space(10)

                  Text {
                    text: modelData.icon
                    color: Color.urgent
                    font.family: Style.font.family
                    font.pixelSize: Style.font.title
                    anchors.verticalCenter: parent.verticalCenter
                  }

                  Column {
                    width: parent.width - Style.space(40)
                    spacing: Style.space(2)

                    Text {
                      text: modelData.name
                      color: Color.foreground
                      font.family: Style.font.family
                      font.pixelSize: Style.font.body
                      font.bold: true
                      elide: Text.ElideRight
                      width: parent.width
                    }

                    Text {
                      text: modelData.type_label + " · ID " + modelData.id + " (" + modelData.vid_pid + ") · Port " + modelData.port
                      color: Color.urgent
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                      font.bold: true
                      elide: Text.ElideRight
                      width: parent.width
                    }
                  }
                }

                Row {
                  spacing: Style.space(6)
                  anchors.right: parent.right

                  Button {
                    text: "Allow (Session)"
                    fontSize: Style.font.caption
                    onClicked: root.allowDevice(modelData.id, false)
                  }

                  Button {
                    text: "Trust (Permanent)"
                    fontSize: Style.font.caption
                    selected: true
                    onClicked: root.allowDevice(modelData.id, true)
                  }

                  Button {
                    text: "Reject"
                    fontSize: Style.font.caption
                    foreground: Color.urgent
                    onClicked: root.rejectDevice(modelData.id)
                  }
                }
              }
            }
          }
        }

        // 4. Tabs
        Row {
          width: parent.width
          spacing: Style.space(6)
          visible: !root.needsSetup

          Button {
            text: "Connected (" + root.visibleCount + ")"
            selected: root.currentTab === "devices"
            onClicked: root.currentTab = "devices"
          }

          Button {
            text: "Whitelist Rules (" + root.rules.length + ")"
            selected: root.currentTab === "rules"
            onClicked: root.currentTab = "rules"
          }
        }

        // 5. Tab 1: Connected Devices
        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: root.currentTab === "devices" && !root.needsSetup

          Text {
            visible: root.visibleCount === 0
            text: "No USB devices connected."
            color: Color.muted
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            topPadding: Style.space(8)
            bottomPadding: Style.space(8)
          }

          Repeater {
            model: root.visibleDevices

            delegate: BorderSurface {
              width: parent.width
              implicitHeight: devRow.implicitHeight + Style.space(16)
              color: modelData.is_blocked
                ? Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.10)
                : Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.03)
              radius: Style.cornerRadius
              borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)

              Row {
                id: devRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Style.space(12)
                anchors.rightMargin: Style.space(12)
                spacing: Style.space(12)

                Text {
                  text: modelData.icon
                  color: modelData.is_blocked ? Color.urgent : (modelData.is_internal ? Color.muted : Color.accent)
                  font.family: Style.font.family
                  font.pixelSize: Style.font.title
                  anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                  width: parent.width - Style.space(130)
                  spacing: Style.space(2)
                  anchors.verticalCenter: parent.verticalCenter

                  Text {
                    text: modelData.name
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                    elide: Text.ElideRight
                    width: parent.width
                  }

                  Text {
                    text: modelData.type_label + " · " + (modelData.is_internal ? "Internal Hardware" : "Port " + modelData.port)
                    color: Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideRight
                    width: parent.width
                  }
                }

                Row {
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(4)

                  Button {
                    visible: modelData.is_allowed && !modelData.is_internal
                    text: "Block"
                    fontSize: Style.font.caption
                    onClicked: root.blockDevice(modelData.id)
                  }

                  Button {
                    visible: modelData.is_blocked
                    text: "Allow"
                    fontSize: Style.font.caption
                    selected: true
                    onClicked: root.allowDevice(modelData.id, false)
                  }

                  Text {
                    visible: modelData.is_internal
                    text: "Internal"
                    color: Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    anchors.verticalCenter: parent.verticalCenter
                  }
                }
              }
            }
          }
        }

        // 6. Tab 2: Whitelist Rules
        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: root.currentTab === "rules" && !root.needsSetup

          Text {
            visible: root.rules.length === 0
            text: "No permanent whitelist rules configured."
            color: Color.muted
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            topPadding: Style.space(8)
            bottomPadding: Style.space(8)
          }

          Repeater {
            model: root.rules

            delegate: BorderSurface {
              width: parent.width
              implicitHeight: ruleRow.implicitHeight + Style.space(14)
              color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.03)
              radius: Style.cornerRadius
              borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)

              Row {
                id: ruleRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Style.space(12)
                anchors.rightMargin: Style.space(12)
                spacing: Style.space(12)

                Text {
                  text: modelData.icon || "󰕥"
                  color: modelData.is_internal ? Color.muted : Color.accent
                  font.family: Style.font.family
                  font.pixelSize: Style.font.title
                  anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                  width: parent.width - (deleteBtn.visible ? Style.space(110) : Style.space(60))
                  spacing: Style.space(2)
                  anchors.verticalCenter: parent.verticalCenter

                  Text {
                    text: modelData.name
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                    elide: Text.ElideRight
                    width: parent.width
                  }

                  Text {
                    text: modelData.subtitle || (modelData.is_internal ? "Internal Hardware" : "Permanent Whitelist")
                    color: Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideRight
                    width: parent.width
                  }
                }

                Button {
                  id: deleteBtn
                  visible: modelData.id !== "" && !modelData.is_internal
                  iconText: "󰅖"
                  tooltipText: "Revoke rule"
                  foreground: Color.urgent
                  onClicked: root.removeRule(modelData.id)
                  anchors.verticalCenter: parent.verticalCenter
                }
              }
            }
          }
        }

        PanelSeparator {}

        // 7. Footer
        Item {
          width: parent.width
          implicitHeight: footerLabel.implicitHeight + Style.space(4)

          Text {
            id: footerLabel
            text: root.daemonActive ? "󰕥 Hardware Protection Active" : "󰅖 USBGuard is inactive"
            color: root.daemonActive ? Color.muted : Color.urgent
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
          }
        }
      }
    }
  }
}
