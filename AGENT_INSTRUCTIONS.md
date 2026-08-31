# INSTRUÇÃO / TASK SPECIFICATION PARA AGENTE IA: Screen-Lock Protection no `omarchy-usbguard`

## 1. Localização e Contexto do Projeto
* **Diretório:** `/home/skyme/omarchy-usbguard`
* **Plugin ID:** `io.github.skymebr.usbguard`
* **Ambiente:** Omarchy Linux (Arch Linux + Hyprland + Quickshell)
* **Status:** Aprovado e publicado na loja oficial de plugins do Omarchy.

`omarchy-usbguard` é um plugin de segurança em nível de kernel para o Omarchy que gerencia permissões de portas USB, protege contra ataques BadUSB (como Rubber Ducky) e oferece um widget nativo de barra em Quickshell (`Panel.qml`).

---

## 2. Componentes Existentes e o que cada um faz

1. **`manifest.json`**: Metadados do plugin e esquema aprovado para a loja do Omarchy.
2. **`Panel.qml`**: Widget nativo da barra e painel popup interativo em Quickshell.
3. **`backend.py`**: Scanner de hardware de alta velocidade (<15ms) consultando `sysfs` e `hwdata`.
4. **`omarchy-usbguard-event`**: Script chamado pelo gancho nativo `usbguard watch -e` quando um novo dispositivo é plugado. Faz classificação por classe hexadecimal (anti-spoofing) e detecção de BadUSB (composição de Mass Storage + HID).
5. **`omarchy-usbguard-allow`**: Script que autoriza dispositivos temporária ou permanentemente, validando hashes SHA-256 para evitar reaproveitamento de IDs.
6. **`omarchy-setup-security-usbguard`**: Assistente de configuração inicial com política anti-lockout para hardware embutido (`allow with-connect-type "hardwired"`).

---

## 3. Diretrizes Rígidas (NÃO MODIFICAR O QUE JÁ FOI APROVADO)

* ⚠️ **NÃO alterar o esquema do `manifest.json`** que quebre a compatibilidade com a loja.
* ⚠️ **NÃO remover a regra de anti-lockout** (`allow with-connect-type "hardwired"` e `PresentDevicePolicy=keep`) do script de setup.
* ⚠️ **NÃO alterar as assinaturas de IPC** entre `omarchy-usbguard-event` e `omarchy-usbguard-allow`.
* ⚠️ **NÃO alterar o `Panel.qml`** a menos que estritamente necessário para integração.

---

## 4. Objetivo Específico: Bloqueio com Tela Travada (Screen Guard)

### O Problema:
Quando a sessão está bloqueada (via `hyprlock` / `hypridle`), a máquina pode estar fisicamente vulnerável. Inserções de novos USBs durante a tela travada NÃO devem disparar menus interativos e DEVEM ser estritamente bloqueadas/rejeitadas no kernel.

### O que o Agente deve implementar:
1. **Verificação de Estado de Bloqueio em `omarchy-usbguard-event`:**
   Adicionar uma função `is_screen_locked()` que detecta:
   * Processos ativos de lockscreen: `hyprlock` ou `swaylock` (`pgrep -x "hyprlock"`).
   * Ou propriedade DBus `LockedHint` de `org.freedesktop.login1`.
2. **Comportamento em Bloqueio:**
   * Se `is_screen_locked()` for verdadeiro:
     - Rejeitar ou manter o dispositivo bloqueado imediatamente (`usbguard reject-device "$USBGUARD_DEVICE_ID" || true`).
     - Suprimir a exibição de popups interativos e menus (`omarchy-menu-select`).
     - Gravar um log seguro em `/run/user/$UID/usbguard-locked-attempts.log` com timestamp, ID do dispositivo e detalhes.
3. **Alerta Pós-Desbloqueio (Opcional/Desejável):**
   * Ao detectar o desbloqueio da tela (ou na próxima inserção), notificar o usuário caso algum dispositivo tenha sido rejeitado durante a ausência dele.

---

## 5. Validações e Testes Obrigatórios

Após qualquer alteração, o agente DEVE rodar:
```bash
# 1. Validar sintaxe dos scripts bash
bash -n /home/skyme/omarchy-usbguard/omarchy-usbguard-event
bash -n /home/skyme/omarchy-usbguard/omarchy-setup-security-usbguard

# 2. Rodar testes de backend
python3 -m unittest /home/skyme/omarchy-usbguard/test_backend.py
```
