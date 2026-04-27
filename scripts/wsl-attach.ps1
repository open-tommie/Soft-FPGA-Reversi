<#
.SYNOPSIS
    Pico 2 / Debug Probe を usbipd-win 経由で WSL2 にバインド + アタッチする。

.DESCRIPTION
    `usbipd state` の JSON 出力から VID:PID で BUSID を自動検出して bind / attach する。
    BUSID は USB ポートを差し替えると変わるが、VID:PID は固定なので追従できる。

    認識する VID:PID:
      2e8a:000a  Pico (stdio_usb / CDC)
      2e8a:000f  Pico 2 (BOOTSEL / RP2350)
      2e8a:0003  Pico (BOOTSEL / RP2040)
      2e8a:000c  Debug Probe (CMSIS-DAP)

.PARAMETER Mode
    list   検出して状態を表示するだけ
    attach bind 済みのデバイスを WSL2 にアタッチ（既定）
    bind   未 bind のデバイスを bind（必要なら自己 UAC 昇格）してから attach
    detach 検出されたデバイスを WSL2 から外す

.EXAMPLE
    PS> .\scripts\wsl-attach.ps1 -Mode list
    PS> .\scripts\wsl-attach.ps1 -Mode bind        # 初回（UAC ダイアログ）
    PS> .\scripts\wsl-attach.ps1                   # 2 回目以降
    PS> .\scripts\wsl-attach.ps1 -Mode detach
#>
[CmdletBinding()]
param(
    [ValidateSet('list', 'attach', 'bind', 'detach')]
    [string]$Mode = 'attach'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Devices = [ordered]@{
    '2e8a:000a' = 'Pico (stdio_usb / CDC)'
    '2e8a:000f' = 'Pico 2 (BOOTSEL / RP2350)'
    '2e8a:0003' = 'Pico (BOOTSEL / RP2040)'
    '2e8a:000c' = 'Debug Probe (CMSIS-DAP)'
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Get-UsbipdDevices {
    if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
        throw "usbipd が見つかりません。`winget install --interactive --exact dorssel.usbipd-win` を先に実行してください。"
    }
    $json = & usbipd state 2>$null | Out-String
    if ([string]::IsNullOrWhiteSpace($json)) {
        throw "usbipd state の取得に失敗しました。usbipd-win >= 4.0 が必要です。"
    }
    return ($json | ConvertFrom-Json).Devices
}

function Find-PicoDevices {
    $all = Get-UsbipdDevices
    $found = @()
    foreach ($vidpid in $Devices.Keys) {
        $vid, $productId = $vidpid.Split(':')
        $pattern = "VID_${vid}&PID_${productId}"
        $match = $all | Where-Object {
            $_.InstanceId -and $_.InstanceId.ToUpper().Contains($pattern.ToUpper())
        } | Select-Object -First 1

        if ($null -ne $match) {
            $found += [pscustomobject]@{
                VidPid      = $vidpid
                Name        = $Devices[$vidpid]
                BusId       = $match.BusId
                IsConnected = -not [string]::IsNullOrEmpty($match.BusId)
                IsBound     = [bool]$match.PersistedGuid
                IsAttached  = [bool]$match.ClientIPAddress
            }
        }
    }
    return $found
}

function Format-Device {
    param($d)
    $state = if (-not $d.IsConnected) { 'Disconnected' }
             elseif ($d.IsAttached)   { 'Attached' }
             elseif ($d.IsBound)      { 'Shared' }
             else                     { 'NotShared' }
    $busid = if ($d.IsConnected) { $d.BusId } else { '-' }
    return ('  BUSID={0,-6}  VID:PID={1}  STATE={2,-12}  {3}' -f $busid, $d.VidPid, $state, $d.Name)
}

# ---- main ----

$found = Find-PicoDevices

if ($found.Count -eq 0) {
    Write-Warning "既知の Pico / Debug Probe が検出できません。USB 接続と BOOTSEL 状態を確認してください。"
    Write-Host '----- usbipd list 全文 -----'
    & usbipd list
    exit 2
}

Write-Host '===== 検出デバイス =====' -ForegroundColor Cyan
foreach ($d in $found) { Write-Host (Format-Device $d) }
Write-Host ''

switch ($Mode) {
    'list' {
        return
    }

    'detach' {
        foreach ($d in $found | Where-Object { $_.IsConnected -and $_.IsAttached }) {
            Write-Host "→ usbipd detach --busid $($d.BusId)"
            & usbipd detach --busid $d.BusId
        }
        return
    }

    default {
        # 物理接続されているデバイスのみ対象
        $connected = @($found | Where-Object IsConnected)
        if ($connected.Count -eq 0) {
            Write-Warning "物理接続中の Pico / Debug Probe がありません。USB 抜き差しを確認してください。"
            exit 2
        }
        $needBind = @($connected | Where-Object { -not $_.IsBound })

        if ($needBind.Count -gt 0) {
            if ($Mode -ne 'bind') {
                Write-Host '===== 未 bind のデバイスがあります =====' -ForegroundColor Yellow
                foreach ($d in $needBind) {
                    Write-Host "  usbipd bind --busid $($d.BusId)   # $($d.Name)"
                }
                Write-Host ''
                Write-Host '管理者 PowerShell で上記を実行するか、このスクリプトを `-Mode bind` で再実行してください。' -ForegroundColor Yellow
                exit 3
            }

            if (-not (Test-IsAdmin)) {
                Write-Host '管理者権限が必要なため自己昇格します（UAC ダイアログが出ます）...' -ForegroundColor Yellow
                $argList = @(
                    '-NoProfile',
                    '-ExecutionPolicy', 'Bypass',
                    '-File', $PSCommandPath,
                    '-Mode', 'bind'
                )
                Start-Process powershell -Verb RunAs -ArgumentList $argList -Wait
                # 昇格セッションが bind を済ませたので、現在の通常権限セッションで attach
                $connected = @((Find-PicoDevices) | Where-Object IsConnected)
            } else {
                foreach ($d in $needBind) {
                    Write-Host "→ usbipd bind --busid $($d.BusId)"
                    & usbipd bind --busid $d.BusId
                }
                $connected = @((Find-PicoDevices) | Where-Object IsConnected)
            }
        }

        foreach ($d in $connected) {
            if ($d.IsAttached) {
                Write-Host "[skip] BUSID=$($d.BusId) は既に attached"
                continue
            }
            Write-Host "→ usbipd attach --wsl --busid $($d.BusId)  ($($d.Name))"
            & usbipd attach --wsl --busid $d.BusId
        }
    }
}

# 確認
Write-Host ''
Write-Host '----- usbipd list (2e8a 抽出) -----'
& usbipd list | Select-String '2e8a' | ForEach-Object { Write-Host "  $($_.Line)" }
