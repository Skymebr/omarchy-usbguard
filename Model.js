// Model helper for Omarchy USBGuard plugin.
// Pure functions for parsing 'usbguard list-devices' and 'usbguard list-rules' outputs.

function parseDevices(rawText) {
  if (!rawText || typeof rawText !== "string") return [];
  var lines = rawText.split("\n");
  var devices = [];

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (!line) continue;

    var dev = parseDeviceLine(line);
    if (dev) {
      devices.push(dev);
    }
  }

  return devices;
}

function parseRules(rawText) {
  if (!rawText || typeof rawText !== "string") return [];
  var lines = rawText.split("\n");
  var rules = [];

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (!line) continue;

    var rule = parseRuleLine(line);
    if (rule) {
      rules.push(rule);
    }
  }

  return rules;
}

function parseDeviceLine(line) {
  // Format: <id>: <target> id <vid:pid> serial "<serial>" name "<name>" hash "<hash>" parent-hash "<parent-hash>" via-port "<via-port>" with-interface <interfaces> with-connect-type "<connect-type>"
  var colonIdx = line.indexOf(":");
  if (colonIdx === -1) return null;

  var idStr = line.substring(0, colonIdx).trim();
  var rest = line.substring(colonIdx + 1).trim();

  var parts = rest.split(/\s+/);
  var target = parts[0] || "unknown";

  var vidPid = extractMatch(rest, /id\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})/);
  var serial = extractQuoted(rest, "serial");
  var name = extractQuoted(rest, "name");
  var hash = extractQuoted(rest, "hash");
  var parentHash = extractQuoted(rest, "parent-hash");
  var viaPort = extractQuoted(rest, "via-port");
  var connectType = extractQuoted(rest, "with-connect-type");

  var ifaces = "";
  var ifaceMatch = rest.match(/with-interface\s+(\{[^}]+\}|[0-9a-fA-F:]+)/);
  if (ifaceMatch) {
    ifaces = ifaceMatch[1].replace(/[\{\}]/g, "").trim();
  }

  var classification = classifyDevice(ifaces, name);

  return {
    id: idStr,
    target: target,
    isAllowed: target === "allow",
    isBlocked: target === "block" || target === "reject",
    isReject: target === "reject",
    vidPid: vidPid || "----:----",
    serial: serial || "",
    name: cleanName(name, vidPid, connectType),
    rawName: name,
    hash: hash || "",
    parentHash: parentHash || "",
    viaPort: viaPort || "",
    connectType: connectType || "",
    isHardwired: connectType === "hardwired",
    isHub: classification.isHub,
    ifaces: ifaces,
    icon: classification.icon,
    typeLabel: classification.typeLabel,
    isBadUsb: classification.isBadUsb,
    riskLevel: classification.riskLevel
  };
}

function parseRuleLine(line) {
  var colonIdx = line.indexOf(":");
  if (colonIdx === -1) {
    var ct = extractQuoted(line, "with-connect-type");
    return {
      id: "",
      target: line.startsWith("allow") ? "allow" : "block",
      name: ct === "hardwired" ? "Hardwired Baseline Rule" : "Global Policy Rule",
      vidPid: "",
      hash: "",
      connectType: ct,
      raw: line,
      isHardwired: line.indexOf('"hardwired"') !== -1
    };
  }

  var idStr = line.substring(0, colonIdx).trim();
  var rest = line.substring(colonIdx + 1).trim();

  var target = rest.split(/\s+/)[0] || "allow";
  var vidPid = extractMatch(rest, /id\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})/);
  var name = extractQuoted(rest, "name");
  var hash = extractQuoted(rest, "hash");
  var connectType = extractQuoted(rest, "with-connect-type");

  return {
    id: idStr,
    target: target,
    vidPid: vidPid || "",
    name: cleanName(name, vidPid, connectType) || ("Whitelist Rule #" + idStr),
    hash: hash || "",
    connectType: connectType || "",
    isHardwired: connectType === "hardwired",
    raw: line
  };
}

function classifyDevice(ifaces, rawName) {
  var hasHid = false;
  var hasStorage = false;
  var hasNet = false;
  var hasAudio = false;
  var hasVideo = false;
  var hasBluetooth = false;
  var hasHub = false;
  var isKbd = false;
  var isMouse = false;

  var codes = ifaces.split(/\s+/);
  for (var i = 0; i < codes.length; i++) {
    var c = codes[i].toLowerCase();
    if (c.indexOf("08:") === 0) hasStorage = true;
    if (c.indexOf("03:") === 0) hasHid = true;
    if (c.indexOf("03:01:01") === 0) isKbd = true;
    if (c.indexOf("03:01:02") === 0) isMouse = true;
    if (c.indexOf("02:") === 0 || c.indexOf("0a:") === 0) hasNet = true;
    if (c.indexOf("01:") === 0) hasAudio = true;
    if (c.indexOf("0e:") === 0 || c.indexOf("10:") === 0) hasVideo = true;
    if (c.indexOf("e0:") === 0) hasBluetooth = true;
    if (c.indexOf("09:") === 0) hasHub = true;
  }

  // BadUSB composite detection (Storage + HID / Storage + Network)
  if (hasStorage && (hasHid || isKbd)) {
    return {
      icon: "󰕤",
      typeLabel: "High-Risk BadUSB (Storage + HID)",
      isBadUsb: true,
      isHub: false,
      riskLevel: "critical"
    };
  }

  if (hasStorage && hasNet) {
    return {
      icon: "󰕤",
      typeLabel: "High-Risk BadUSB (Storage + Net)",
      isBadUsb: true,
      isHub: false,
      riskLevel: "critical"
    };
  }

  if (isKbd) {
    return { icon: "󰌌", typeLabel: "Keyboard", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (isMouse) {
    return { icon: "󰍽", typeLabel: "Mouse", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasHid) {
    return { icon: "󰌌", typeLabel: "Human Interface (HID)", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasStorage) {
    return { icon: "󰕒", typeLabel: "Mass Storage", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasAudio) {
    return { icon: "󰓗", typeLabel: "Audio Device", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasVideo) {
    return { icon: "󰄀", typeLabel: "Camera / Video", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasNet) {
    return { icon: "󰖩", typeLabel: "Network Adapter", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasBluetooth) {
    return { icon: "󰂯", typeLabel: "Wireless / Bluetooth", isBadUsb: false, isHub: false, riskLevel: "info" };
  }
  if (hasHub) {
    return { icon: "󰕓", typeLabel: "USB Root Hub", isBadUsb: false, isHub: true, riskLevel: "info" };
  }

  return { icon: "󰕓", typeLabel: "USB Peripheral", isBadUsb: false, isHub: false, riskLevel: "info" };
}

function cleanName(rawName, vidPid, connectType) {
  if (!rawName || rawName === "USB Device" || rawName === "Mass Storage" || rawName === "Wireless_Device") {
    if (connectType === "hardwired" && vidPid) return "Internal Device (" + vidPid + ")";
    if (vidPid) return "Device (" + vidPid + ")";
    if (connectType === "hardwired") return "Internal USB Hardware";
    return "USB Device";
  }
  return rawName.replace(/^[-_\s]+/, "").trim();
}

function extractMatch(str, regex) {
  var m = str.match(regex);
  return m ? m[1] : "";
}

function extractQuoted(str, key) {
  var re = new RegExp('(?:^|\\s)' + key + '\\s+"([^"]*)"');
  var m = str.match(re);
  return m ? m[1] : "";
}
