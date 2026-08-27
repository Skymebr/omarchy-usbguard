import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "io.github.skymebr.usbguard"
  ipcTarget: "io.github.skymebr.usbguard"
  manageIpc: false

  property bool daemonActive: false
  property string currentTab: "devices" // "devices" | "rules"
  property string rawDevicesOutput: ""
  property string rawRulesOutput: ""

  readonly property bool hideHubs: setting("hideHubs", true) === true
  readonly property bool showBlockedBadge: setting("showBlockedBadge", true) === true

  readonly property var devices: Model.parseDevices(rawDevicesOutput)
  readonly property var rules: Model.parseRules(rawRulesOutput)

  readonly property var visibleDevices: devices.filter(function(d) {
    return !root.hideHubs || !d.isHub
  })

  readonly property var blockedDevices: visibleDevices.filter(function(d) {
    return d.isBlocked
  })

  readonly property var badUsbDevices: visibleDevices.filter(function(d) {
    return d.isBadUsb
  })

  readonly property bool hasBlocked: blockedDevices.length > 0
  readonly property bool hasBadUsb: badUsbDevices.length > 0

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
    if (!statusProc.running) {
      statusProc.command = ["systemctl", "is-active", "usbguard.service"]
      statusProc.running = true
    }
    if (!devicesProc.running) {
      devicesProc.command = ["usbguard", "list-devices"]
      devicesProc.running = true
    }
    if (!rulesProc.running) {
      rulesProc.command = ["usbguard", "list-rules"]
      rulesProc.running = true
    }
  }

  function allowDevice(devId, permanent) {
    if (!devId) return
    var cmd = permanent
      ? ["usbguard", "allow-device", String(devId), "-p"]
      : ["usbguard", "allow-device", String(devId)]
    runAction(cmd)
  }

  function blockDevice(devId) {
    if (!devId) return
    runAction(["usbguard", "block-device", String(devId)])
  }

  function rejectDevice(devId) {
    if (!devId) return
    runAction(["usbguard", "reject-device", String(devId)])
  }

  function removeRule(ruleId) {
    if (!ruleId) return
    runAction(["usbguard", "remove-rule", String(ruleId)])
  }

  function runAction(cmd) {
    actionProc.command = cmd
    actionProc.running = true
  }

  Component.onCompleted: refresh()

  Process {
    id: statusProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.daemonActive = (text || "").trim() === "active"
      }
    }
  }

  Process {
    id: devicesProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.rawDevicesOutput = text || ""
      }
    }
  }

  Process {
    id: rulesProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.rawRulesOutput = text || ""
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
      ? root.barIcon + " " + root.blockedDevices.length
      : root.barIcon
    slotSize: Style.bar.iconSlot * (root.hasBlocked && root.showBlockedBadge && !vertical ? 1.7 : 1)
    tooltipText: root.daemonActive
      ? (root.hasBlocked
          ? root.blockedDevices.length + " USB device(s) blocked!"
          : "USBGuard: Protected (" + root.visibleDevices.length + " devices)")
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
          meta: root.daemonActive
            ? (root.hasBadUsb ? "BADUSB THREAT DETECTED" : (root.hasBlocked ? root.blockedDevices.length + " BLOCKED DEVICE(S)" : root.visibleDevices.length + " CONNECTED"))
            : "SERVICE INACTIVE"
          iconComponent: Component {
            Text {
              text: root.hasBadUsb ? "󰕤" : (root.hasBlocked ? "󰌾" : "󰕥")
              color: root.hasBadUsb || root.hasBlocked ? Color.urgent : (root.daemonActive ? Color.accent : Color.muted)
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

        // 2. Alert Banner for Blocked / BadUSB Devices
        Column {
          width: parent.width
          spacing: Style.space(8)
          visible: root.hasBlocked

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
                anchors.margins: Style.space(10)
                spacing: Style.space(8)

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
                      text: modelData.typeLabel + " · ID " + modelData.id + " (" + modelData.vidPid + ")"
                      color: Color.urgent
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                      font.bold: true
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

        // 3. Tabs
        Row {
          width: parent.width
          spacing: Style.space(6)

          Button {
            text: "Connected (" + root.visibleDevices.length + ")"
            selected: root.currentTab === "devices"
            onClicked: root.currentTab = "devices"
          }

          Button {
            text: "Whitelist Rules (" + root.rules.length + ")"
            selected: root.currentTab === "rules"
            onClicked: root.currentTab = "rules"
          }
        }

        // 4. Connected Devices
        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: root.currentTab === "devices"

          Text {
            visible: root.visibleDevices.length === 0
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
              implicitHeight: devRow.implicitHeight + Style.space(14)
              color: modelData.isBlocked
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
                  color: modelData.isBlocked ? Color.urgent : (modelData.isHardwired ? Color.muted : Color.accent)
                  font.family: Style.font.family
                  font.pixelSize: Style.font.title
                  anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                  width: parent.width - Style.space(140)
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
                    text: modelData.typeLabel + " · " + (modelData.isHardwired ? "Internal Hardware" : "Port " + modelData.viaPort)
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
                    visible: modelData.isAllowed && !modelData.isHardwired
                    text: "Block"
                    fontSize: Style.font.caption
                    onClicked: root.blockDevice(modelData.id)
                  }

                  Button {
                    visible: modelData.isBlocked
                    text: "Allow"
                    fontSize: Style.font.caption
                    selected: true
                    onClicked: root.allowDevice(modelData.id, false)
                  }

                  Text {
                    visible: modelData.isHardwired
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

        // 5. Whitelist Rules
        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: root.currentTab === "rules"

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
                  text: "󰕥"
                  color: Color.accent
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
                    text: (modelData.vidPid ? "ID: " + modelData.vidPid + " · " : "") + (modelData.isHardwired ? "Hardwired baseline" : "Permanent allow")
                    color: Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideRight
                    width: parent.width
                  }
                }

                Button {
                  id: deleteBtn
                  visible: modelData.id !== "" && !modelData.isHardwired
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

        // 6. Footer
        Row {
          width: parent.width

          Text {
            text: root.daemonActive ? "󰕥 Hardware Protection Active" : "󰅖 usbguard.service is stopped"
            color: root.daemonActive ? Color.muted : Color.urgent
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            anchors.verticalCenter: parent.verticalCenter
          }

          Item {
            Layout.fillWidth: true
            width: Math.max(0, parent.width - parent.children[0].implicitWidth - footerBtn.implicitWidth - Style.space(8))
            height: 1
          }

          Button {
            id: footerBtn
            text: "Setup Wizard"
            fontSize: Style.font.caption
            onClicked: {
              Process.execDetached(["omarchy-launch-terminal", "--", "omarchy-setup-security-usbguard"])
            }
          }
        }
      }
    }
  }
}
