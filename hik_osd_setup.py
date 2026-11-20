#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康摄像头 OSD 预置工具 —— 为 MATE-X3 移动式主板准备 OsdToken_102

用法：
  检查（不改任何配置）
    python hik_osd_setup.py --check 192.168.1.100 admin 密码

  单台部署
    python hik_osd_setup.py 192.168.1.100 admin 密码

  批量部署（设备清单.txt 每行：IP,用户名,密码）
    python hik_osd_setup.py --file 设备清单.txt

  删除（回滚）
    python hik_osd_setup.py --remove 192.168.1.100 admin 密码

参数：
  --text "GAS 0.0%LEL"     占位文字，默认 GAS 0.0%%LEL
  --pos -0.85 0.75         归一化坐标，默认 -0.85 0.75（左下）
  --font 32                字号，默认 32
  --expect OsdToken_102    期望的 token 名，默认 OsdToken_102
  --dry-run                等同 --check
"""
import csv
import datetime
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request

TIMEOUT = 8
PATH = "/onvif/media2_service"
DEVPATH = "/onvif/device_service"

ENV = ('<?xml version="1.0" encoding="UTF-8"?>'
       '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
       'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
       'xmlns:tt="http://www.onvif.org/ver10/schema" '
       'xmlns:tr2="http://www.onvif.org/ver20/media/wsdl">'
       '<s:Body>%s</s:Body></s:Envelope>')


class Cam:
    def __init__(self, ip, user, pwd):
        self.ip, self.user, self.pwd = ip, user, pwd
        self.auth = {}

    def _send(self, path, body):
        h = {"Content-Type": "application/soap+xml; charset=utf-8"}
        if path in self.auth:
            h["Authorization"] = self.auth[path]
        req = urllib.request.Request("http://%s%s" % (self.ip, path),
                                     data=body.encode("utf-8"), headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=TIMEOUT)
            return r.status, r.read(30000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read(8000).decode("utf-8", "replace")
        except Exception as e:
            return -1, "%s: %s" % (type(e).__name__, e)

    def call(self, soap, path=PATH):
        body = ENV % soap
        st, txt = self._send(path, body)
        if st == 401:
            # 先拿 nonce
            req = urllib.request.Request(
                "http://%s%s" % (self.ip, path), data=body.encode("utf-8"),
                headers={"Content-Type": "application/soap+xml; charset=utf-8"})
            try:
                urllib.request.urlopen(req, timeout=TIMEOUT)
            except urllib.error.HTTPError as e:
                wa = e.headers.get("WWW-Authenticate") or ""
            except Exception:
                return -1, "认证握手失败"
            p = dict(re.findall(r'(\w+)="([^"]*)"', wa))
            realm, nonce, qop = p.get("realm", ""), p.get("nonce", ""), p.get("qop", "auth")
            ha1 = hashlib.md5(("%s:%s:%s" % (self.user, realm, self.pwd)).encode()).hexdigest()
            ha2 = hashlib.md5(("POST:%s" % path).encode()).hexdigest()
            cn = os.urandom(8).hex()
            rsp = hashlib.md5(("%s:%s:00000001:%s:%s:%s" % (ha1, nonce, cn, qop, ha2)).encode()).hexdigest()
            auth = ('Digest username="%s", realm="%s", nonce="%s", uri="%s", qop=%s, nc=00000001, '
                    'cnonce="%s", response="%s", algorithm=MD5' % (self.user, realm, nonce, path, qop, cn, rsp))
            if p.get("opaque"):
                auth += ', opaque="%s"' % p["opaque"]
            self.auth[path] = auth
            st, txt = self._send(path, body)
        return st, txt

    # ---------- 具体操作 ----------
    def info(self):
        st, txt = self.call("<tds:GetDeviceInformation/>", DEVPATH)
        if st != 200:
            return {}
        out = {}
        for tag, key in (("Manufacturer", "厂商"), ("Model", "型号"),
                         ("FirmwareVersion", "固件"), ("SerialNumber", "序列号")):
            m = re.search(r"<(?:(?:tt|tds|trt|hik):)?%s>([^<]*)</" % tag, txt)
            if m:
                out[key] = m.group(1)
        return out

    def osds(self):
        st, txt = self.call("<tr2:GetOSDs/>")
        if st != 200:
            return None, txt
        rows = []
        for m in re.finditer(r'<tr2:OSDs token="([^"]+)">(.*?)</tr2:OSDs>', txt, re.S):
            body = m.group(2)
            t = re.search(r"<tt:PlainText>(.*?)</tt:PlainText>", body, re.S)
            d = re.search(r"<tt:Type>(DateAndTime|Plain)</tt:Type>", body)
            rows.append({"token": m.group(1),
                         "type": d.group(1) if d else "?",
                         "text": t.group(1) if t else ""})
        return rows, txt

    def create(self, text, pos, font):
        soap = ('<tr2:CreateOSD><tr2:OSD>'
                '<tt:VideoSourceConfigurationToken>VideoSourceToken</tt:VideoSourceConfigurationToken>'
                '<tt:Type>Text</tt:Type>'
                '<tt:Position><tt:Type>Custom</tt:Type>'
                '<tt:Pos x="%s" y="%s"/></tt:Position>'
                '<tt:TextString><tt:Type>Plain</tt:Type>'
                '<tt:PlainText>%s</tt:PlainText>'
                '<tt:FontSize>%s</tt:FontSize></tt:TextString>'
                '</tr2:OSD></tr2:CreateOSD>') % (pos[0], pos[1], _xml(text), font)
        return self.call(soap)

    def set_text(self, token, block, text):
        nb = re.sub(r"<tt:PlainText>.*?</tt:PlainText>",
                    "<tt:PlainText>%s</tt:PlainText>" % _xml(text), block, flags=re.S)
        return self.call('<tr2:SetOSD><tr2:OSD token="%s">%s</tr2:OSD></tr2:SetOSD>' % (token, nb))

    def block(self, token):
        st, txt = self.call("<tr2:GetOSDs/>")
        if st != 200:
            return None
        m = re.search(r'<tr2:OSDs token="%s">(.*?)</tr2:OSDs>' % re.escape(token), txt, re.S)
        return m.group(1) if m else None

    def delete(self, token):
        return self.call('<tr2:DeleteOSD><tr2:OSDToken>%s</tr2:OSDToken></tr2:DeleteOSD>' % token)


def _xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def deploy(ip, user, pwd, text, pos, font, expect, check_only, remove):
    rec = {"时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "IP": ip,
           "型号": "", "序列号": "", "固件": "", "原OSD数": "", "动作": "", "token": "",
           "结果": "", "备注": ""}
    c = Cam(ip, user, pwd)

    info = c.info()          # 拿不到设备信息不阻断，后面以 GetOSDs 是否成功为准
    rec.update({"型号": info.get("型号", ""), "序列号": info.get("序列号", ""),
                "固件": info.get("固件", "")})

    rows, raw = c.osds()
    if rows is None:
        rec["结果"] = "失败"
        rec["备注"] = "GetOSDs 失败：%s" % raw[:120].replace("\n", " ")
        return rec
    rec["原OSD数"] = len(rows)
    tokens = [r["token"] for r in rows]

    # ---- 删除模式 ----
    if remove:
        if expect not in tokens:
            rec["动作"] = "无需删除"
            rec["结果"] = "成功"
            rec["备注"] = "%s 不存在" % expect
            return rec
        st, txt = c.delete(expect)
        rec["动作"] = "删除"
        rec["token"] = expect
        rec["结果"] = "成功" if st == 200 else "失败"
        rec["备注"] = "" if st == 200 else "DeleteOSD 返回 %s" % st
        return rec

    # ---- 已存在 ----
    if expect in tokens:
        rec["动作"] = "复用"
        rec["token"] = expect
        if check_only:
            rec["结果"] = "成功"
            rec["备注"] = "已存在，无需创建"
            return rec
        blk = c.block(expect)
        if blk:
            st, _ = c.set_text(expect, blk, text)
            rec["结果"] = "成功" if st == 200 else "部分成功"
            rec["备注"] = "已存在并已写入占位文字" if st == 200 else "已存在，但写文字失败 %s" % st
        else:
            rec["结果"] = "成功"
            rec["备注"] = "已存在（未改文字）"
        return rec

    # ---- 不存在 ----
    if check_only:
        rec["动作"] = "待创建"
        rec["结果"] = "需处理"
        rec["备注"] = "当前 tokens=%s，%s 不存在" % (",".join(tokens), expect)
        return rec

    before = set(tokens)
    st, txt = c.create(text, pos, font)
    if st != 200:
        rec["动作"] = "新建"
        rec["结果"] = "失败"
        rec["备注"] = "CreateOSD 返回 %s" % st
        return rec

    time.sleep(0.8)
    rows2, _ = c.osds()
    after = set(r["token"] for r in (rows2 or []))
    new = sorted(after - before)
    if not new:
        rec["动作"] = "新建"
        rec["结果"] = "失败"
        rec["备注"] = "CreateOSD 返回 200 但 OSD 列表未变化"
        return rec

    tok = new[0]
    rec["token"] = tok
    rec["动作"] = "新建"
    if tok == expect:
        rec["结果"] = "成功"
        rec["备注"] = "位置 (%s, %s)，文字 %s" % (pos[0], pos[1], text)
    else:
        c.delete(tok)
        rec["结果"] = "需处理"
        rec["备注"] = "自动分配为 %s，与期望 %s 不符，已删除；该型号需固件适配" % (tok, expect)
    return rec


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = sys.argv[1:]
    if not args or args[0] in ("--menu", "-m"):
        return menu()
    return run(args)


def _ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except EOFError:
        return default
    return v if v else default


def menu():
    while True:
        print()
        print("=" * 56)
        print("   海康摄像头 OSD 预置工具   (MATE-X3 / OsdToken_102)")
        print("=" * 56)
        print("   1  检查（只读，不改任何配置）")
        print("   2  单台部署")
        print("   3  批量部署（读取 设备清单.txt）")
        print("   4  删除 OsdToken_102（回滚）")
        print("   0  退出")
        print()
        ch = _ask("   请选择: ")
        if ch == "0":
            return 0
        if ch == "3":
            if not os.path.exists("设备清单.txt"):
                print("   找不到 设备清单.txt")
                continue
            run(["--file", "设备清单.txt"])
            print()
            _ask("   按回车返回菜单...")
            continue
        if ch not in ("1", "2", "4"):
            print("   无效选择")
            continue
        ip = _ask("   摄像头 IP : ")
        u = _ask("   用户名    : ")
        pw = _ask("   密码      : ")
        if not ip:
            print("   未输入 IP")
            continue
        if ch == "1":
            run(["--check", ip, u, pw])
        elif ch == "2":
            t = _ask("   占位文字（回车用默认 GAS 0.0%LEL）: ", "GAS 0.0%LEL")
            run([ip, u, pw, "--text", t])
        else:
            ok = _ask("   确认删除？(Y/N): ")
            if ok.lower() == "y":
                run(["--remove", ip, u, pw])
        print()
        _ask("   按回车返回菜单...")


def run(args):
    if not args:
        print(__doc__)
        return 2

    text = "GAS 0.0%LEL"
    pos = ["-0.85", "0.75"]
    font = "32"
    expect = "OsdToken_102"
    check_only = False
    remove = False
    devices = []

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--check", "--dry-run"):
            check_only = True
        elif a == "--remove":
            remove = True
        elif a == "--text":
            i += 1
            text = args[i]
        elif a == "--pos":
            pos = [args[i + 1], args[i + 2]]
            i += 2
        elif a == "--font":
            i += 1
            font = args[i]
        elif a == "--expect":
            i += 1
            expect = args[i]
        elif a == "--file":
            i += 1
            with open(args[i], encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = [x.strip() for x in re.split(r"[,，\t]", line)]
                    if len(parts) >= 3:
                        devices.append(parts[:3])
        else:
            devices.append([a, args[i + 1] if i + 1 < len(args) else "",
                            args[i + 2] if i + 2 < len(args) else ""])
            i += 2
        i += 1

    if not devices:
        print("没有指定设备。用法见 --help")
        return 2

    print("=" * 62)
    print("海康摄像头 OSD 预置  |  期望 token: %s  |  模式: %s"
          % (expect, "删除" if remove else ("检查" if check_only else "部署")))
    print("=" * 62)

    recs = []
    for dev in devices:
        ip, user, pwd = dev[0], dev[1], dev[2]
        if not pwd:
            print("[跳过] %s 缺少账号或密码" % ip)
            continue
        r = deploy(ip, user, pwd, text, pos, font, expect, check_only, remove)
        recs.append(r)
        print("[%s] %-15s %-22s %-6s %-12s %s"
              % (r["结果"], ip, r["型号"][:22], r["动作"], r["token"], r["备注"][:40]))

    if recs:
        fn = "OSD部署记录_%s.csv" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(fn, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
            w.writeheader()
            w.writerows(recs)
        print("\n记录已保存：%s" % os.path.abspath(fn))

    ok = sum(1 for r in recs if r["结果"] == "成功")
    print("合计 %d 台，成功 %d 台" % (len(recs), ok))
    return 0 if ok == len(recs) else 1


if __name__ == "__main__":
    sys.exit(main())
