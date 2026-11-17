"""Local Web Dashboard for FDFS Ticket Radar (Zero Extra Dependencies)."""

import json
import logging
import os
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import Settings
from notifiers.ntfy_notifier import NtfyNotifier

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#070a12">
  <title>FDFS Ticket Radar — 24/7 Command Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #070a13;
      --surface: rgba(15, 23, 42, 0.75);
      --surface-card: rgba(22, 33, 58, 0.65);
      --surface-hover: rgba(30, 45, 78, 0.8);
      --border: rgba(255, 255, 255, 0.08);
      --border-glow: rgba(0, 242, 254, 0.25);
      --primary: #ff2a5f;
      --primary-glow: rgba(255, 42, 95, 0.35);
      --cyan: #00f2fe;
      --cyan-glow: rgba(0, 242, 254, 0.3);
      --emerald: #10b981;
      --emerald-glow: rgba(16, 185, 129, 0.35);
      --amber: #f59e0b;
      --amber-glow: rgba(245, 158, 11, 0.3);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body {
      background: radial-gradient(circle at 50% 0%, #151e36 0%, #090d18 55%, #05070d 100%);
      background-attachment: fixed;
      color: var(--text);
      padding: 16px;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }
    .container { max-width: 920px; margin: 0 auto; padding-bottom: 90px; }
    
    /* Header & Nav */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-title {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .brand-title span {
      background: linear-gradient(135deg, #ff2a5f 0%, #ff7e5f 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand-badge {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      padding: 3px 8px;
      border-radius: 6px;
      background: rgba(0, 242, 254, 0.12);
      color: var(--cyan);
      border: 1px solid rgba(0, 242, 254, 0.3);
      letter-spacing: 0.5px;
    }
    
    /* Buttons */
    .btn {
      background: var(--primary);
      color: white;
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 9px 16px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      text-decoration: none;
      box-shadow: 0 4px 12px var(--primary-glow);
    }
    .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 18px var(--primary-glow);
      filter: brightness(1.1);
    }
    .btn:active { transform: translateY(0); }
    .btn-secondary {
      background: rgba(30, 41, 59, 0.8);
      color: #cbd5e1;
      border: 1px solid var(--border);
      box-shadow: none;
    }
    .btn-secondary:hover {
      background: rgba(51, 65, 85, 0.9);
      color: white;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    .btn-cyan {
      background: rgba(0, 242, 254, 0.15);
      color: var(--cyan);
      border: 1px solid rgba(0, 242, 254, 0.3);
      box-shadow: 0 4px 12px var(--cyan-glow);
    }
    .btn-cyan:hover {
      background: rgba(0, 242, 254, 0.25);
      box-shadow: 0 6px 16px var(--cyan-glow);
    }
    .btn-danger {
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
      box-shadow: none;
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.3);
      color: white;
    }
    .btn-sm { padding: 6px 12px; font-size: 12px; border-radius: 6px; }

    /* FDFS Segmented Buttons */
    .btn-fdfs-active {
      background: #ff2a5f !important;
      color: white !important;
      border: 1px solid rgba(255, 42, 95, 0.6) !important;
      box-shadow: 0 0 14px rgba(255, 42, 95, 0.45) !important;
      font-weight: 700 !important;
    }
    .btn-all-active {
      background: #00f2fe !important;
      color: #070a13 !important;
      border: 1px solid rgba(0, 242, 254, 0.6) !important;
      box-shadow: 0 0 14px rgba(0, 242, 254, 0.45) !important;
      font-weight: 800 !important;
    }
    .btn-fdfs-inactive {
      background: rgba(30, 41, 59, 0.6) !important;
      color: #94a3b8 !important;
      border: 1px solid var(--border) !important;
      box-shadow: none !important;
      font-weight: 500 !important;
    }
    
    /* Telemetry / Hero Command Bar */
    .telemetry-card {
      background: var(--surface);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 20px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      position: relative;
      overflow: hidden;
    }
    .telemetry-card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, var(--emerald), var(--cyan), var(--primary));
    }
    .telemetry-grid {
      display: grid;
      grid-template-columns: auto 1fr 1fr 1fr;
      gap: 16px;
      align-items: center;
    }
    @media (max-width: 768px) {
      .telemetry-grid {
        grid-template-columns: 1fr 1fr;
      }
      .radar-visual-col {
        grid-column: span 2;
        justify-content: center;
      }
    }
    
    /* Circular Radar Graphic */
    .radar-visual-col {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .radar-box {
      position: relative;
      width: 58px;
      height: 58px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(16, 185, 129, 0.1) 0%, rgba(6, 78, 59, 0.3) 100%);
      border: 1.5px solid rgba(16, 185, 129, 0.4);
      box-shadow: 0 0 16px rgba(16, 185, 129, 0.25), inset 0 0 12px rgba(16, 185, 129, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    .radar-box::before {
      content: "";
      position: absolute;
      width: 65%;
      height: 65%;
      border-radius: 50%;
      border: 1px dashed rgba(16, 185, 129, 0.3);
    }
    .radar-sweep {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      border-radius: 50%;
      background: conic-gradient(from 0deg, rgba(16, 185, 129, 0.45) 0deg, transparent 65deg, transparent 360deg);
      animation: radarSweep 2.4s linear infinite;
    }
    .radar-blip {
      position: absolute;
      width: 5px; height: 5px;
      background: var(--cyan);
      border-radius: 50%;
      box-shadow: 0 0 6px var(--cyan);
      animation: blipFade 1.6s ease-in-out infinite;
    }
    @keyframes radarSweep {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes blipFade {
      0%, 100% { opacity: 0.2; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1.3); }
    }
    
    .stat-widget {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .stat-label {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .stat-value {
      font-size: 16px;
      font-weight: 800;
      color: var(--text);
      font-family: 'JetBrains Mono', monospace;
    }
    .stat-sub {
      font-size: 11px;
      color: var(--text-dim);
    }
    
    /* Live Targets List */
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 22px 0 14px 0;
    }
    .section-title {
      font-size: 17px;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .target-card {
      background: var(--surface-card);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 16px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .target-card:hover {
      border-color: rgba(255, 255, 255, 0.16);
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
    }
    .target-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .target-title-box {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .target-movie-name {
      font-size: 18px;
      font-weight: 800;
      color: #fff;
      letter-spacing: -0.3px;
    }
    .pill {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      padding: 3px 8px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }
    .pill-city {
      background: rgba(148, 163, 184, 0.15);
      color: #cbd5e1;
      border: 1px solid rgba(148, 163, 184, 0.25);
    }
    .pill-fdfs {
      background: rgba(255, 42, 95, 0.15);
      color: #ff6b8b;
      border: 1px solid rgba(255, 42, 95, 0.3);
    }
    .pill-all {
      background: rgba(0, 242, 254, 0.15);
      color: var(--cyan);
      border: 1px solid rgba(0, 242, 254, 0.3);
    }
    
    /* Platform Deck */
    .platform-deck {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 14px;
    }
    @media (max-width: 640px) {
      .platform-deck { grid-template-columns: 1fr; }
    }
    .platform-box {
      background: rgba(10, 15, 29, 0.65);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transition: all 0.2s ease;
    }
    .platform-box:hover {
      background: rgba(15, 23, 42, 0.85);
      border-color: rgba(255, 255, 255, 0.14);
    }
    .platform-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .platform-name {
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      display: flex;
      align-items: center;
      gap: 6px;
      color: #e2e8f0;
    }
    .platform-badge {
      font-size: 11px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 5px;
      font-family: 'JetBrains Mono', monospace;
    }
    .status-open {
      background: rgba(16, 185, 129, 0.2);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
      animation: pulseAlert 1.5s infinite;
    }
    .status-partial {
      background: rgba(245, 158, 11, 0.2);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .status-closed {
      background: rgba(100, 116, 139, 0.2);
      color: #94a3b8;
      border: 1px solid rgba(100, 116, 139, 0.3);
    }
    @keyframes pulseAlert {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.85; transform: scale(1.02); }
    }
    .platform-status-text {
      font-size: 12px;
      color: #cbd5e1;
      line-height: 1.4;
    }
    .platform-link-btn {
      font-size: 11px;
      font-weight: 600;
      color: var(--cyan);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      margin-top: 2px;
      transition: color 0.15s ease;
    }
    .platform-link-btn:hover {
      color: #fff;
      text-decoration: underline;
    }
    
    /* Target Theatres & Regex Bar */
    .filter-summary-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      background: rgba(8, 12, 22, 0.5);
      border-radius: 8px;
      border: 1px solid var(--border);
      font-size: 12px;
    }
    .theatre-chip {
      background: rgba(59, 130, 246, 0.15);
      color: #93c5fd;
      border: 1px solid rgba(59, 130, 246, 0.25);
      padding: 2px 8px;
      border-radius: 5px;
      font-weight: 600;
      font-size: 11px;
    }
    .regex-chip {
      background: rgba(168, 85, 247, 0.15);
      color: #d8b4fe;
      border: 1px solid rgba(168, 85, 247, 0.25);
      padding: 2px 8px;
      border-radius: 5px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
    }
    
    /* Live Detected Shows Box */
    .live-shows-banner {
      margin-top: 12px;
      background: rgba(225, 29, 72, 0.15);
      border: 1.5px solid rgba(225, 29, 72, 0.4);
      border-radius: 10px;
      padding: 12px;
      box-shadow: 0 0 20px rgba(225, 29, 72, 0.2);
    }
    .live-shows-title {
      font-size: 13px;
      font-weight: 800;
      color: #fda4af;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
    }
    .live-shows-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 8px;
    }
    .show-tile {
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(255, 42, 95, 0.3);
      border-radius: 8px;
      padding: 8px 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .show-venue {
      font-size: 12px;
      font-weight: 700;
      color: #fff;
    }
    .show-time-badge {
      font-size: 11px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
      color: #34d399;
      background: rgba(16, 185, 129, 0.15);
      padding: 2px 6px;
      border-radius: 4px;
    }
    
    /* Accordion Edit Form */
    .edit-drawer {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border);
      display: none;
    }
    .edit-drawer.open { display: block; }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    @media (max-width: 640px) {
      .form-grid { grid-template-columns: 1fr; }
    }
    .full-width { grid-column: span 2; }
    @media (max-width: 640px) { .full-width { grid-column: span 1; } }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    label {
      font-size: 11px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    input, select {
      background: rgba(10, 15, 28, 0.85);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 12px;
      color: white;
      font-size: 13px;
      outline: none;
      transition: border-color 0.2s ease;
      width: 100%;
    }
    input:focus, select:focus {
      border-color: var(--cyan);
      box-shadow: 0 0 10px rgba(0, 242, 254, 0.2);
    }
    
    /* Terminal Console Drawer */
    .terminal-card {
      background: #050811;
      border: 1px solid rgba(0, 242, 254, 0.2);
      border-radius: 12px;
      margin-top: 24px;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
      overflow: hidden;
    }
    .terminal-header {
      background: rgba(15, 23, 42, 0.8);
      padding: 10px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
    }
    .terminal-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 700;
      color: var(--cyan);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .terminal-logs {
      padding: 12px 14px;
      max-height: 220px;
      overflow-y: auto;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      line-height: 1.6;
      color: #94a3b8;
    }
    .log-line {
      display: flex;
      gap: 8px;
      margin-bottom: 4px;
    }
    .log-time { color: #64748b; }
    .log-round { color: var(--cyan); font-weight: 700; }
    .log-text { color: #cbd5e1; }
    .log-text.highlight { color: #34d399; font-weight: 700; }
    
    /* Toast */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: rgba(16, 185, 129, 0.95);
      backdrop-filter: blur(8px);
      color: white;
      padding: 12px 20px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 13px;
      display: none;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
      z-index: 1000;
      animation: toastSlide 0.3s ease;
    }
    @keyframes toastSlide {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    
    /* Mobile Floating Dock */
    .mobile-dock {
      display: none;
      position: fixed;
      bottom: 0; left: 0; right: 0;
      background: rgba(7, 10, 19, 0.88);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-top: 1px solid var(--border);
      padding: 10px 16px;
      z-index: 99;
      justify-content: space-around;
      gap: 8px;
    }
    @media (max-width: 640px) {
      .mobile-dock { display: flex; }
      .header-actions { display: none; }
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <div class="brand">
        <div class="brand-title">🎟️ <span>FDFS</span> RADAR</div>
        <div class="brand-badge">24/7 ONLINE</div>
      </div>
      <div class="header-actions" style="display: flex; gap: 8px;">
        <button class="btn btn-cyan btn-sm" id="btn-scan-top" onclick="triggerScanNow()">⚡ Scan Now</button>
        <button class="btn btn-secondary btn-sm" onclick="pingStatus()">📱 Ping Phone</button>
        <button class="btn btn-secondary btn-sm" onclick="testSiren()">🚨 Test Siren</button>
        <button class="btn btn-sm" onclick="saveAll()">💾 Save</button>
      </div>
    </div>

    <!-- Telemetry Command Center -->
    <div class="telemetry-card">
      <div class="telemetry-grid">
        <!-- Radar Sweep Graphic -->
        <div class="radar-visual-col">
          <div class="radar-box">
            <div class="radar-sweep"></div>
            <div class="radar-blip" style="top: 25%; left: 60%;"></div>
            <div class="radar-blip" style="top: 65%; left: 35%; animation-delay: 0.8s;"></div>
          </div>
          <div>
            <div style="font-size: 15px; font-weight: 800; color: #fff;">Radar Command</div>
            <div id="radar-live-state" style="font-size: 12px; color: var(--emerald); font-weight: 700; display: flex; align-items: center; gap: 4px;">
              <span style="display:inline-block; width:6px; height:6px; background:var(--emerald); border-radius:50%;"></span>
              Active (Round #<span id="tele-round">0</span>)
            </div>
          </div>
        </div>

        <!-- Next Scan Ticker -->
        <div class="stat-widget">
          <div class="stat-label">⏱️ Next Sweep In</div>
          <div class="stat-value" id="countdown-val">--s</div>
          <div class="stat-sub" id="last-checked-time">Last: Loading...</div>
        </div>

        <!-- Monitored Titles -->
        <div class="stat-widget">
          <div class="stat-label">🎬 Target Movies</div>
          <div class="stat-value" id="stats-movies-count">0 Titles</div>
          <div class="stat-sub">BMS + District Active</div>
        </div>

        <!-- Detected Tickets -->
        <div class="stat-widget">
          <div class="stat-label">🚨 Live Booking</div>
          <div class="stat-value" id="stats-matches-count" style="color: var(--emerald);">Scanning...</div>
          <div class="stat-sub" id="stats-status-text">All quiet</div>
        </div>
      </div>
    </div>

    <!-- Phone Siren Channel & Mobile Notification Setup -->
    <div class="target-card" style="margin-bottom: 24px; border: 1px solid rgba(0, 242, 254, 0.4); background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(20, 30, 48, 0.85) 100%);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
        <div style="flex: 1; min-width: 280px;">
          <div style="font-size: 15px; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 8px;">
            <span>🔔</span> Phone Siren Topic: 
            <code style="background: rgba(0, 242, 254, 0.15); color: var(--cyan); padding: 3px 10px; border-radius: 6px; font-size: 14px; font-weight: 700;" id="ntfy-topic-display">saravanan-fdfs-siren-7781</code>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px; line-height: 1.6;">
            <b>Why notifications might not pop up on your phone:</b>
            <div style="margin-top: 4px; display: flex; flex-direction: column; gap: 4px;">
              <div>1️⃣ <b>Subscribe in app:</b> Open ntfy app &amp; subscribe to <span id="ntfy-topic-guide" style="color: var(--cyan); font-weight: 700;">saravanan-fdfs-siren-7781</span>.</div>
              <div>2️⃣ <b>Android Notification Permission:</b> Make sure phone allows <i>"All Notifications"</i> for the ntfy app.</div>
              <div>3️⃣ <b>Battery Optimization:</b> Set ntfy battery setting to <i>"Unrestricted"</i> so alerts pop when screen is locked.</div>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
          <a href="ntfy://ntfy.sh/saravanan-fdfs-siren-7781" id="ntfy-app-link" class="btn btn-cyan btn-sm">📲 Open in ntfy App</a>
          <a href="https://ntfy.sh/saravanan-fdfs-siren-7781" id="ntfy-web-link" target="_blank" class="btn btn-secondary btn-sm">🌐 Web Feed</a>
          <button class="btn btn-sm" style="background: #ff2a5f; color: white;" onclick="testSiren()">🚨 Test Siren</button>
        </div>
      </div>
    </div>

    <!-- Main Section: Targets -->
    <div class="section-header">
      <div class="section-title">
        <span>🎬</span> Monitored Targets (<span id="target-count-badge">0</span>)
      </div>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-secondary btn-sm" onclick="showPresetModal()">✨ Quick Presets</button>
        <button class="btn btn-sm" onclick="addMovieCard()">➕ Add Movie</button>
      </div>
    </div>

    <!-- Movie Targets List Container -->
    <div id="movies-list"></div>

    <!-- Terminal Radar Console -->
    <div class="terminal-card">
      <div class="terminal-header">
        <div class="terminal-title">
          <span>📟</span> LIVE RADAR TELEMETRY LOGS
        </div>
        <button class="btn btn-secondary btn-sm" style="font-size: 11px; padding: 4px 8px;" onclick="toggleTerminal()">Toggle Console</button>
      </div>
      <div class="terminal-logs" id="terminal-logs-body">
        <div class="log-line">
          <span class="log-time">[System]</span>
          <span class="log-text">Connecting to 24/7 background radar thread...</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Mobile Bottom Floating Action Bar -->
  <div class="mobile-dock">
    <button class="btn btn-cyan btn-sm" style="flex: 1;" onclick="triggerScanNow()">⚡ Scan</button>
    <button class="btn btn-secondary btn-sm" style="flex: 1;" onclick="pingStatus()">📱 Ping</button>
    <button class="btn btn-secondary btn-sm" style="flex: 1;" onclick="testSiren()">🚨 Siren</button>
    <button class="btn btn-sm" style="flex: 1.2;" onclick="saveAll()">💾 Save</button>
  </div>

  <div id="toast" class="toast">Saved successfully!</div>

  <script>
    let watchlist = [];
    let radarStatus = null;
    let nextCheckSeconds = 45;
    let countdownInterval = null;
    const openDrawers = new Set(); // Tracks open edit drawers so they never close unexpectedly!

    async function loadWatchlist() {
      try {
        const res = await fetch('/api/watchlist');
        const data = await res.json();
        watchlist = data.watchlist || [];
        const topic = data.ntfy_topic || 'saravanan-fdfs-siren-7781';
        const topicEl = document.getElementById('ntfy-topic-display');
        const guideEl = document.getElementById('ntfy-topic-guide');
        const appLink = document.getElementById('ntfy-app-link');
        const webLink = document.getElementById('ntfy-web-link');
        if (topicEl) topicEl.innerText = topic;
        if (guideEl) guideEl.innerText = topic;
        if (appLink) appLink.href = `ntfy://ntfy.sh/${topic}`;
        if (webLink) webLink.href = `https://ntfy.sh/${topic}`;
        document.getElementById('target-count-badge').innerText = watchlist.length;
        document.getElementById('stats-movies-count').innerText = `${watchlist.length} Titles`;
        render();
      } catch (e) {
        console.error('Error loading watchlist', e);
      }
    }

    async function loadLiveStatus() {
      try {
        const res = await fetch('/api/status');
        radarStatus = await res.json();
        updateTelemetryUI();
      } catch (e) {
        console.error('Error loading radar status', e);
      }
    }

    function updateTelemetryUI() {
      if (!radarStatus) return;

      const roundEl = document.getElementById('tele-round');
      if (roundEl) roundEl.innerText = radarStatus.scan_round || 1;

      // Calculate time ago
      if (radarStatus.last_scan_timestamp) {
        const d = new Date(radarStatus.last_scan_timestamp * 1000);
        const localTime = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
        const secAgo = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
        const agoStr = secAgo < 60 ? `${secAgo}s ago` : `${Math.floor(secAgo / 60)}m ago`;
        const lastEl = document.getElementById('last-checked-time');
        if (lastEl) lastEl.innerText = `Last: ${localTime} (${agoStr})`;
      }

      // Next check countdown
      if (radarStatus.next_scan_timestamp) {
        nextCheckSeconds = Math.max(0, Math.floor(radarStatus.next_scan_timestamp - (Date.now() / 1000)));
      }

      // Check matches count
      let totalMatches = 0;
      if (radarStatus.movies) {
        radarStatus.movies.forEach(m => totalMatches += (m.matched_shows_count || 0));
      }

      const matchVal = document.getElementById('stats-matches-count');
      const statusText = document.getElementById('stats-status-text');
      if (matchVal && statusText) {
        if (totalMatches > 0) {
          matchVal.innerHTML = `<span style="color: #ff2a5f;">🔥 ${totalMatches} SHOWS</span>`;
          statusText.innerText = 'TICKETS AVAILABLE!';
        } else {
          matchVal.innerHTML = `<span style="color: #10b981;">0 Live</span>`;
          statusText.innerText = 'Scanning catalog...';
        }
      }

      // Render terminal logs
      renderTerminalLogs(radarStatus.recent_logs || []);

      // In-place update of status cards WITHOUT destroying open edit drawers or inputs!
      if (radarStatus.movies) {
        radarStatus.movies.forEach(m => {
          const item = watchlist.find(w => (m.id && w.id === m.id) || (w.movie_name || '').toLowerCase().trim() === (m.movie_name || '').toLowerCase().trim());
          if (item) {
            const bmsStatusEl = document.getElementById(`bms-status-text-${item.id}`);
            const bmsBadgeEl = document.getElementById(`bms-badge-${item.id}`);
            const bmsLinkEl = document.getElementById(`bms-link-${item.id}`);

            if (bmsStatusEl) bmsStatusEl.innerText = m.bms_status || 'Scanning...';
            if (bmsBadgeEl) {
              const isOpen = (m.bms_status || '').includes('OPEN');
              const isWarn = (m.bms_status || '').includes('⚠️');
              bmsBadgeEl.className = `platform-badge ${isOpen ? 'status-open' : (isWarn ? 'status-partial' : 'status-closed')}`;
              bmsBadgeEl.innerText = isOpen ? '🔥 OPEN' : (isWarn ? '⚠️ PARTIAL' : '⏳ CLOSED');
            }
            if (bmsLinkEl && m.bms_url) bmsLinkEl.href = m.bms_url;

            const distStatusEl = document.getElementById(`dist-status-text-${item.id}`);
            const distBadgeEl = document.getElementById(`dist-badge-${item.id}`);
            const distLinkEl = document.getElementById(`dist-link-${item.id}`);

            if (distStatusEl) distStatusEl.innerText = m.district_status || 'Scanning...';
            if (distBadgeEl) {
              const isOpen = (m.district_status || '').includes('OPEN');
              const isWarn = (m.district_status || '').includes('⚠️');
              distBadgeEl.className = `platform-badge ${isOpen ? 'status-open' : (isWarn ? 'status-partial' : 'status-closed')}`;
              distBadgeEl.innerText = isOpen ? '🔥 OPEN' : (isWarn ? '⚠️ PARTIAL' : '⏳ CLOSED');
            }
            if (distLinkEl && m.district_url) distLinkEl.href = m.district_url;

            // Live Show Booking Tiles (in-place update)
            const bannerEl = document.getElementById(`live-shows-banner-${item.id}`);
            if (bannerEl) {
              const matched = m.matched_shows_list || [];
              if (matched.length > 0) {
                bannerEl.style.display = 'block';
                bannerEl.innerHTML = `
                  <div class="live-shows-title">🔥 TICKETS DETECTED! IMMEDIATE BOOKING LINKS:</div>
                  <div class="live-shows-grid">
                    ${matched.map(s => `
                      <div class="show-tile">
                        <div>
                          <div class="show-venue">${s.theatre}</div>
                          <div style="font-size: 11px; color: var(--text-muted);">${s.format} • ${s.platform}</div>
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                          <span class="show-time-badge">${s.time}</span>
                          <a href="${s.booking_url}" target="_blank" class="btn btn-sm" style="padding: 2px 8px; font-size: 11px;">⚡ Book</a>
                        </div>
                      </div>
                    `).join('')}
                  </div>
                `;
              } else {
                bannerEl.style.display = 'none';
                bannerEl.innerHTML = '';
              }
            }
          }
        });
      }
    }

    function renderTerminalLogs(logs) {
      const body = document.getElementById('terminal-logs-body');
      if (!logs || logs.length === 0 || !body) return;

      body.innerHTML = logs.map(l => `
        <div class="log-line">
          <span class="log-time">[${l.time}]</span>
          <span class="log-round">[R#${l.round}]</span>
          <span class="log-text ${l.total_matches > 0 ? 'highlight' : ''}">${l.summary}</span>
        </div>
      `).join('');
    }

    function startCountdownTicker() {
      if (countdownInterval) clearInterval(countdownInterval);
      countdownInterval = setInterval(() => {
        const el = document.getElementById('countdown-val');
        if (!el) return;
        if (nextCheckSeconds > 0) {
          nextCheckSeconds--;
          el.innerText = `${nextCheckSeconds}s`;
        } else {
          el.innerText = `Scanning...`;
        }
      }, 1000);
    }

    function render() {
      const container = document.getElementById('movies-list');
      if (!container) return;

      if (watchlist.length === 0) {
        container.innerHTML = `
          <div class="target-card" style="text-align: center; color: var(--text-muted); padding: 45px;">
            <div style="font-size: 32px; margin-bottom: 10px;">🎬</div>
            <div style="font-weight: 700; font-size: 16px; color: #fff;">No movies in radar watchlist</div>
            <div style="font-size: 13px; margin: 8px 0 16px 0;">Add a movie to start autonomous 24/7 scanning on BookMyShow & District!</div>
            <button class="btn btn-sm" onclick="addMovieCard()">➕ Add Your First Movie</button>
          </div>
        `;
        return;
      }

      // Map status from radarStatus
      const statusMap = {};
      if (radarStatus && radarStatus.movies) {
        radarStatus.movies.forEach(m => {
          statusMap[m.movie_name.toLowerCase().trim()] = m;
        });
      }

      container.innerHTML = watchlist.map((item) => {
        const mKey = (item.movie_name || '').toLowerCase().trim();
        const live = statusMap[mKey] || {};

        const bmsStatus = live.bms_status || 'Waiting for first scan...';
        const distStatus = live.district_status || 'Waiting for first scan...';
        const bmsUrl = live.bms_url || item.bms_url || `https://in.bookmyshow.com/explore/movies-${(item.district || 'chennai').toLowerCase()}`;
        const distUrl = live.district_url || item.district_url || `https://www.district.in/movies`;
        const matchedShows = live.matched_shows_list || [];

        const bmsBadgeClass = bmsStatus.includes('OPEN') ? 'status-open' : (bmsStatus.includes('⚠️') ? 'status-partial' : 'status-closed');
        const distBadgeClass = distStatus.includes('OPEN') ? 'status-open' : (distStatus.includes('⚠️') ? 'status-partial' : 'status-closed');

        const isOpen = openDrawers.has(item.id);

        return `
          <div class="target-card" id="card-${item.id}">
            <!-- Header -->
            <div class="target-header">
              <div class="target-title-box">
                <span style="font-size: 20px;">🎬</span>
                <span class="target-movie-name" id="title-text-${item.id}">${item.movie_name || 'Untitled Movie'}</span>
                <span class="pill pill-city" id="pill-city-${item.id}">${item.district || 'All Districts'}</span>
                <span class="pill ${item.fdfs_only !== false ? 'pill-fdfs' : 'pill-all'}" id="pill-fdfs-${item.id}">
                  ${item.fdfs_only !== false ? '⚡ FDFS (≤ 08:00 AM)' : '⏰ Any Time'}
                </span>
                ${item.target_date ? `<span class="pill pill-city" id="pill-date-${item.id}">📅 ${item.target_date}</span>` : ''}
              </div>
              <div style="display: flex; gap: 6px; align-items: center;">
                <button class="btn btn-secondary btn-sm" id="btn-edit-${item.id}" onclick="toggleEdit('${item.id}')">
                  ${isOpen ? '▲ Close' : '⚙️ Edit'}
                </button>
                <button class="btn btn-danger btn-sm" onclick="deleteMovie('${item.id}')">🗑️</button>
              </div>
            </div>

            <!-- Platform Dual Cards -->
            <div class="platform-deck">
              <!-- BookMyShow Box -->
              <div class="platform-box">
                <div class="platform-header">
                  <span class="platform-name">🎟️ BookMyShow</span>
                  <span class="platform-badge ${bmsBadgeClass}" id="bms-badge-${item.id}">${bmsStatus.includes('OPEN') ? '🔥 OPEN' : (bmsStatus.includes('⚠️') ? '⚠️ PARTIAL' : '⏳ CLOSED')}</span>
                </div>
                <div class="platform-status-text" id="bms-status-text-${item.id}">${bmsStatus}</div>
                <a href="${bmsUrl}" id="bms-link-${item.id}" target="_blank" class="platform-link-btn">
                  🔗 Open BookMyShow Target Page &rarr;
                </a>
              </div>

              <!-- District by Zomato Box -->
              <div class="platform-box">
                <div class="platform-header">
                  <span class="platform-name">🎟️ District by Zomato</span>
                  <span class="platform-badge ${distBadgeClass}" id="dist-badge-${item.id}">${distStatus.includes('OPEN') ? '🔥 OPEN' : (distStatus.includes('⚠️') ? '⚠️ PARTIAL' : '⏳ CLOSED')}</span>
                </div>
                <div class="platform-status-text" id="dist-status-text-${item.id}">${distStatus}</div>
                <a href="${distUrl}" id="dist-link-${item.id}" target="_blank" class="platform-link-btn">
                  🔗 Open District Target Page &rarr;
                </a>
              </div>
            </div>

            <!-- Theatres & Active Matcher -->
            <div class="filter-summary-bar">
              <span style="color: var(--text-muted); font-weight: 700;">THEATRES:</span>
              <span id="theatres-chips-${item.id}" style="display: flex; gap: 6px; flex-wrap: wrap;">
                ${(item.target_theatres && item.target_theatres.length > 0)
                  ? item.target_theatres.map(t => `<span class="theatre-chip">${t}</span>`).join('')
                  : '<span class="theatre-chip" style="background: rgba(16, 185, 129, 0.15); color: #6ee7b7;">ALL THEATRES in District</span>'}
              </span>
              
              <span style="margin-left: auto; color: var(--text-dim); display: flex; align-items: center; gap: 4px;">
                <span>🔍</span>
                <span class="regex-chip" id="regex-chip-${item.id}">
                  ${item.movie_regex ? `/${item.movie_regex}/i` : `Auto: /${(item.movie_name || '').replace(/\\s+/g, '[\\\\s\\\\.\\\\-_]*')}/i`}
                </span>
              </span>
            </div>

            <!-- Live Available Shows Banner (if any) -->
            <div id="live-shows-banner-${item.id}" class="live-shows-banner" style="display: ${(matchedShows && matchedShows.length > 0) ? 'block' : 'none'};">
              ${(matchedShows && matchedShows.length > 0) ? `
                <div class="live-shows-title">🔥 TICKETS DETECTED! IMMEDIATE BOOKING LINKS:</div>
                <div class="live-shows-grid">
                  ${matchedShows.map(s => `
                    <div class="show-tile">
                      <div>
                        <div class="show-venue">${s.theatre}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">${s.format} • ${s.platform}</div>
                      </div>
                      <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                        <span class="show-time-badge">${s.time}</span>
                        <a href="${s.booking_url}" target="_blank" class="btn btn-sm" style="padding: 2px 8px; font-size: 11px;">⚡ Book</a>
                      </div>
                    </div>
                  `).join('')}
                </div>
              ` : ''}
            </div>

            <!-- Collapsible Edit Drawer -->
            <div id="edit-drawer-${item.id}" class="edit-drawer ${isOpen ? 'open' : ''}">
              <div class="form-grid">
                <div class="form-group">
                  <label>Movie Name / Title</label>
                  <input type="text" 
                         value="${item.movie_name || ''}" 
                         oninput="updateMovieField('${item.id}', 'movie_name', this.value)" 
                         placeholder="e.g. Coolie, O.M, Scene">
                </div>

                <div class="form-group">
                  <label>Custom Movie Regex (Optional)</label>
                  <input type="text" 
                         value="${item.movie_regex || ''}" 
                         oninput="updateMovieField('${item.id}', 'movie_regex', this.value)" 
                         placeholder="e.g. O\\.?M.*, Thalapathy\\s*(69|T69)">
                </div>

                <div class="form-group">
                  <label>District / City</label>
                  <input type="text" 
                         value="${item.district || ''}" 
                         oninput="updateMovieField('${item.id}', 'district', this.value)" 
                         placeholder="e.g. Chennai, Coimbatore, Madurai">
                </div>

                <div class="form-group">
                  <label>Release Date (Optional)</label>
                  <input type="text" 
                         value="${item.target_date || ''}" 
                         oninput="updateMovieField('${item.id}', 'target_date', this.value)" 
                         placeholder="YYYY-MM-DD or leave blank">
                </div>

                <div class="form-group full-width">
                  <label>Target Theatres (comma-separated, or 'all')</label>
                  <input type="text" 
                         id="theatres-input-${item.id}"
                         value="${(item.target_theatres || []).join(', ')}" 
                         oninput="updateTheatresField('${item.id}', this.value)" 
                         placeholder="e.g. Rohini, Vettri, AGS, KG Cinemas">
                  <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
                    <span style="font-size: 11px; color: var(--text-dim);">Quick Add:</span>
                    <a href="javascript:void(0)" onclick="appendTheatre('${item.id}', 'Rohini Silver Screens')" class="theatre-chip">+ Rohini</a>
                    <a href="javascript:void(0)" onclick="appendTheatre('${item.id}', 'Vettri Theatres')" class="theatre-chip">+ Vettri</a>
                    <a href="javascript:void(0)" onclick="appendTheatre('${item.id}', 'AGS Cinemas')" class="theatre-chip">+ AGS</a>
                    <a href="javascript:void(0)" onclick="appendTheatre('${item.id}', 'KG Cinemas')" class="theatre-chip">+ KG Cinemas</a>
                    <a href="javascript:void(0)" onclick="appendTheatre('${item.id}', 'PVR')" class="theatre-chip">+ PVR</a>
                    <a href="javascript:void(0)" onclick="appendTheatre('${item.id}', 'Miraj')" class="theatre-chip">+ Miraj</a>
                  </div>
                </div>

                <!-- 100% Reliable FDFS Segmented Buttons -->
                <div class="form-group full-width">
                  <label>Timing / Show Filter</label>
                  <div style="display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap;">
                    <button type="button" 
                            id="fdfs-btn-on-${item.id}"
                            class="btn btn-sm ${item.fdfs_only !== false ? 'btn-fdfs-active' : 'btn-fdfs-inactive'}" 
                            onclick="setFDFSOption('${item.id}', true)">
                      ⚡ Early Morning FDFS (≤ 08:00 AM)
                    </button>
                    <button type="button" 
                            id="fdfs-btn-off-${item.id}"
                            class="btn btn-sm ${item.fdfs_only === false ? 'btn-all-active' : 'btn-fdfs-inactive'}" 
                            onclick="setFDFSOption('${item.id}', false)">
                      ⏰ All Shows (Any Time of Day)
                    </button>
                  </div>
                </div>

                <div class="form-group">
                  <label>Direct BMS URL (Optional)</label>
                  <input type="text" 
                         value="${item.bms_url || ''}" 
                         oninput="updateMovieField('${item.id}', 'bms_url', this.value)" 
                         placeholder="https://in.bookmyshow.com/movies/...">
                </div>

                <div class="form-group">
                  <label>Direct District URL (Optional)</label>
                  <input type="text" 
                         value="${item.district_url || ''}" 
                         oninput="updateMovieField('${item.id}', 'district_url', this.value)" 
                         placeholder="https://www.district.in/movies/...">
                </div>
              </div>

              <!-- Drawer Bottom Actions -->
              <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border);">
                <button type="button" class="btn btn-secondary btn-sm" onclick="toggleEdit('${item.id}')">Cancel</button>
                <button type="button" class="btn btn-sm" style="background: var(--emerald); box-shadow: 0 4px 12px var(--emerald-glow);" onclick="doneAndSave('${item.id}')">✅ Done & Save</button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function toggleEdit(id) {
      const drawer = document.getElementById(`edit-drawer-${id}`);
      const btn = document.getElementById(`btn-edit-${id}`);
      if (!drawer) return;
      if (openDrawers.has(id)) {
        openDrawers.delete(id);
        drawer.classList.remove('open');
        if (btn) btn.innerHTML = '⚙️ Edit';
      } else {
        openDrawers.add(id);
        drawer.classList.add('open');
        if (btn) btn.innerHTML = '▲ Close';
      }
    }

    function doneAndSave(id) {
      openDrawers.delete(id);
      const drawer = document.getElementById(`edit-drawer-${id}`);
      const btn = document.getElementById(`btn-edit-${id}`);
      if (drawer) drawer.classList.remove('open');
      if (btn) btn.innerHTML = '⚙️ Edit';
      saveAll();
    }

    function updateMovieField(id, field, value) {
      const item = watchlist.find(w => w.id === id);
      if (!item) return;
      item[field] = value;

      // Real-time title updates without re-rendering or closing drawers!
      if (field === 'movie_name') {
        const titleEl = document.getElementById(`title-text-${id}`);
        if (titleEl) titleEl.innerText = value || 'Untitled Movie';
        const regexChip = document.getElementById(`regex-chip-${id}`);
        if (regexChip && !item.movie_regex) {
          regexChip.innerText = `Auto: /${(value || '').replace(/\\s+/g, '[\\\\s\\\\.\\\\-_]*')}/i`;
        }
      } else if (field === 'district') {
        const cityEl = document.getElementById(`pill-city-${id}`);
        if (cityEl) cityEl.innerText = value || 'All Districts';
      } else if (field === 'movie_regex') {
        const regexChip = document.getElementById(`regex-chip-${id}`);
        if (regexChip) {
          regexChip.innerText = value ? `/${value}/i` : `Auto: /${(item.movie_name || '').replace(/\\s+/g, '[\\\\s\\\\.\\\\-_]*')}/i`;
        }
      }
    }

    function setFDFSOption(id, isFDFS) {
      const item = watchlist.find(w => w.id === id);
      if (!item) return;
      item.fdfs_only = isFDFS;

      // Visually toggle buttons immediately with active styling
      const btnOn = document.getElementById(`fdfs-btn-on-${id}`);
      const btnOff = document.getElementById(`fdfs-btn-off-${id}`);
      if (btnOn && btnOff) {
        if (isFDFS) {
          btnOn.className = 'btn btn-sm btn-fdfs-active';
          btnOff.className = 'btn btn-sm btn-fdfs-inactive';
        } else {
          btnOn.className = 'btn btn-sm btn-fdfs-inactive';
          btnOff.className = 'btn btn-sm btn-all-active';
        }
      }

      // Update card title pill
      const pill = document.getElementById(`pill-fdfs-${id}`);
      if (pill) {
        if (isFDFS) {
          pill.className = 'pill pill-fdfs';
          pill.innerText = '⚡ FDFS (≤ 08:00 AM)';
        } else {
          pill.className = 'pill pill-all';
          pill.innerText = '⏰ Any Time (All Day)';
        }
      }
      showToast(isFDFS ? 'Set to: Early Morning FDFS Only' : 'Set to: All Show Times (Any Time)');
      saveAll();
    }

    function updateTheatresField(id, text) {
      const item = watchlist.find(w => w.id === id);
      if (!item) return;
      if (!text || text.trim().toLowerCase() === 'all') {
        item.target_theatres = [];
      } else {
        item.target_theatres = text.split(',').map(s => s.trim()).filter(Boolean);
      }
      updateTheatresDisplay(id, item.target_theatres);
    }

    function appendTheatre(id, theatre) {
      const item = watchlist.find(w => w.id === id);
      if (!item) return;
      if (!item.target_theatres) item.target_theatres = [];
      if (!item.target_theatres.includes(theatre)) {
        item.target_theatres.push(theatre);
        const input = document.getElementById(`theatres-input-${id}`);
        if (input) input.value = item.target_theatres.join(', ');
        updateTheatresDisplay(id, item.target_theatres);
      }
    }

    function updateTheatresDisplay(id, list) {
      const container = document.getElementById(`theatres-chips-${id}`);
      if (!container) return;
      if (list && list.length > 0) {
        container.innerHTML = list.map(t => `<span class="theatre-chip">${t}</span>`).join('');
      } else {
        container.innerHTML = `<span class="theatre-chip" style="background: rgba(16, 185, 129, 0.15); color: #6ee7b7;">ALL THEATRES in District</span>`;
      }
    }

    function addMovieCard(preset = null) {
      const newId = 'movie_' + Date.now();
      const newItem = preset || {
        id: newId,
        movie_name: '',
        movie_regex: null,
        district: 'Chennai',
        target_theatres: [],
        target_date: null,
        fdfs_only: false,
        fdfs_max_time: '08:00',
        enabled: true
      };
      if (preset) newItem.id = newId;

      watchlist.unshift(newItem);
      openDrawers.add(newId); // Keep the new card's edit drawer open!
      document.getElementById('target-count-badge').innerText = watchlist.length;
      document.getElementById('stats-movies-count').innerText = `${watchlist.length} Titles`;
      render();
    }

    function showPresetModal() {
      const choice = prompt(
        "Choose an Upcoming Movie Preset to Add:\n" +
        "1. Coolie (Chennai - Rohini, Vettri, AGS)\n" +
        "2. Thalapathy 69 (Chennai - Rohini, AGS)\n" +
        "3. Good Bad Ugly (Chennai - Rohini, Vettri)\n" +
        "4. Scene (Coimbatore - All Theatres)\n" +
        "Enter number [1-4]:"
      );

      if (choice === "1") {
        addMovieCard({
          movie_name: 'Coolie',
          movie_regex: 'Coolie.*',
          district: 'Chennai',
          target_theatres: ['Rohini Silver Screens', 'Vettri Theatres', 'AGS Cinemas'],
          fdfs_only: false,
          fdfs_max_time: '08:00',
          enabled: true
        });
      } else if (choice === "2") {
        addMovieCard({
          movie_name: 'Thalapathy 69',
          movie_regex: 'Thalapathy\\s*(?:69|T69)',
          district: 'Chennai',
          target_theatres: ['Rohini Silver Screens', 'AGS Cinemas'],
          fdfs_only: false,
          fdfs_max_time: '08:00',
          enabled: true
        });
      } else if (choice === "3") {
        addMovieCard({
          movie_name: 'Good Bad Ugly',
          movie_regex: 'Good[\\s\\.\\-_]*Bad[\\s\\.\\-_]*Ugly',
          district: 'Chennai',
          target_theatres: ['Rohini Silver Screens', 'Vettri Theatres'],
          fdfs_only: false,
          fdfs_max_time: '08:00',
          enabled: true
        });
      } else if (choice === "4") {
        addMovieCard({
          movie_name: 'Scene',
          movie_regex: 'Scene',
          district: 'Coimbatore',
          target_theatres: [],
          fdfs_only: false,
          fdfs_max_time: '08:00',
          enabled: true
        });
      }
    }

    function deleteMovie(id) {
      const item = watchlist.find(w => w.id === id);
      if (confirm(`Remove "${item?.movie_name || 'this movie'}" from radar?`)) {
        openDrawers.delete(id);
        watchlist = watchlist.filter(w => w.id !== id);
        document.getElementById('target-count-badge').innerText = watchlist.length;
        document.getElementById('stats-movies-count').innerText = `${watchlist.length} Titles`;
        render();
        saveAll();
      }
    }

    async function triggerScanNow() {
      const btn = document.getElementById('btn-scan-top');
      if (btn) btn.innerText = '⚡ Scanning...';
      try {
        await fetch('/api/scan-now', { method: 'POST' });
        showToast('⚡ Instant scan triggered! Refreshing radar telemetry...');
        setTimeout(async () => {
          await loadLiveStatus();
          if (btn) btn.innerText = '⚡ Scan Now';
        }, 2200);
      } catch (e) {
        showToast('Error triggering scan');
        if (btn) btn.innerText = '⚡ Scan Now';
      }
    }

    async function saveAll() {
      const topicEl = document.getElementById('ntfy-topic-display');
      const ntfy_topic = topicEl ? topicEl.innerText.trim() : 'saravanan-fdfs-siren-7781';
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ntfy_topic, watchlist })
      });
      showToast('💾 Watchlist updated! Radar scanner synced.');
    }

    async function testSiren() {
      const topicEl = document.getElementById('ntfy-topic-display');
      const topic = (topicEl ? topicEl.innerText.trim() : 'saravanan-fdfs-siren-7781') || 'saravanan-fdfs-siren-7781';

      showToast(`🚨 Dispatching test siren to ${topic}...`);

      let delivered = false;

      // 1. Direct browser push to ntfy.sh (Fastest, zero cloud proxy blocks, works on every mobile browser)
      try {
        const directResp = await fetch(`https://ntfy.sh/${topic}`, {
          method: 'POST',
          body: `🚨 TEST EMERGENCY SIREN!\nYour phone is connected to '${topic}'.\nLock-screen sirens & 1-tap booking will ring here when tickets drop!`,
          headers: {
            'Title': 'FDFS Ticket Radar Siren Test!',
            'Priority': '5',
            'Tags': 'rotating_light,white_check_mark,ticket',
            'Click': `https://ntfy.sh/${topic}`,
            'Actions': `view, Open ntfy Web, https://ntfy.sh/${topic}`
          }
        });
        if (directResp.ok) delivered = true;
      } catch (err) {
        console.warn('Browser direct ntfy push error, falling back to server backend:', err);
      }

      // 2. Also dispatch from server backend to verify server-to-phone pipeline
      try {
        const srvResp = await fetch('/api/test-siren', { method: 'POST' });
        const res = await srvResp.json();
        if (res.status === 'ok') delivered = true;
      } catch (err) {
        console.warn('Server test-siren call failed:', err);
      }

      if (delivered) {
        showToast(`🚨 Test siren delivered to ntfy.sh/${topic}! Check your phone.`);
      } else {
        showToast(`⚠️ Could not reach ntfy.sh/${topic}. Check your internet connection.`);
      }
    }

    async function pingStatus() {
      await fetch('/api/ping-status', { method: 'POST' });
      showToast('📱 Status summary dispatched to your phone lock screen!');
    }

    function toggleTerminal() {
      const el = document.getElementById('terminal-logs-body');
      if (el) {
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
      }
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      if (!toast) return;
      toast.innerText = msg;
      toast.style.display = 'block';
      setTimeout(() => { toast.style.display = 'none'; }, 3200);
    }

    // Initialize
    loadWatchlist();
    loadLiveStatus();
    startCountdownTicker();
    setInterval(loadLiveStatus, 10000); // Poll status every 10s
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """Handles web UI requests and watchlist API."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif self.path in ("/health", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "alive", "service": "fdfs-ticket-radar"}')

        elif self.path == "/api/status":
            data = {"is_running": True, "scan_round": 0, "last_scan_time": "Initializing...", "movies": []}
            if Settings.STATUS_PATH.exists():
                try:
                    with open(Settings.STATUS_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif self.path == "/api/watchlist":
            data = {"watchlist": [], "ntfy_topic": Settings.get_ntfy_topic()}
            if Settings.WATCHLIST_PATH.exists():
                with open(Settings.WATCHLIST_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if not data.get("ntfy_topic"):
                data["ntfy_topic"] = Settings.get_ntfy_topic()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""

        if self.path == "/api/watchlist":
            try:
                payload = json.loads(body)
                Settings.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(Settings.WATCHLIST_PATH, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

        elif self.path == "/api/test-siren":
            topic = Settings.get_ntfy_topic()
            notifier = NtfyNotifier(topic)
            success = notifier.send_test_alert()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok" if success else "error", "topic": topic}).encode("utf-8"))

        elif self.path == "/api/scan-now":
            try:
                from radar import trigger_instant_scan
                trigger_instant_scan()
            except Exception:
                flag = Settings.BASE_DIR / "config" / "trigger_scan.flag"
                flag.touch(exist_ok=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "message": "Instant scan triggered"}')

        elif self.path == "/api/ping-status":
            data = {}
            if Settings.STATUS_PATH.exists():
                try:
                    with open(Settings.STATUS_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            round_num = data.get("scan_round", 1)
            last_time = data.get("last_scan_time", "Just now")
            movies = [m.get("movie_name") for m in data.get("movies", [])]
            body_text = f"Round #{round_num} at {last_time}.\nMonitoring: {', '.join(movies) or 'Active watchlist'}\nStatus: Radar scanning 24/7!"

            try:
                import httpx
                topic = Settings.get_ntfy_topic()
                httpx.post(
                    f"https://ntfy.sh/{topic}",
                    headers={
                        "Title": f"Radar Status: Round #{round_num}",
                        "Priority": "3",
                        "Tags": "satellite,white_check_mark",
                    },
                    data=body_text.encode("utf-8"),
                    timeout=5,
                )
            except Exception:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet logging


def start_server(port: int = None, open_browser: bool = True):
    if port is None:
        port = int(os.environ.get("PORT", "5055"))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    url = f"http://localhost:{port}"
    print("=" * 60)
    print("  🎟️  FDFS TICKET RADAR — 24/7 COMMAND DASHBOARD")
    print("=" * 60)
    print(f"👉 Dashboard listening on: {url} (Port {port})")
    print("   (Access remotely using your cloud domain or local IP)")
    print("=" * 60)

    # Open local browser only in desktop environment
    if open_browser and not os.environ.get("PORT"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    start_server()
