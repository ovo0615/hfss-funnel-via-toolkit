// 此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。
import { useState, useEffect, useRef, useMemo } from 'react';
import { connectAedt, releaseAedt, readStackup, grabVias, buildFunnels } from './api';
import Preview3D from './components/Preview3D';
import { buildScene } from './geometry';

const DEFAULT_STACKUP = `# 格式：kind,name,thickness[,layer]
# kind = soldermask / copper / dielectric ；copper 需填 layer 編號
soldermask,SM_top,0.80
copper,L1,1.20,1
dielectric,pp,2.30
copper,L2,1.20,2
dielectric,pp,3.30
copper,L3,1.00,3
dielectric,pp,3.30
copper,L4,1.20,4
dielectric,pp,3.30
copper,L5,1.20,5
dielectric,CORE,4.00
copper,L6,1.20,6
dielectric,pp,3.30
copper,L7,1.20,7
dielectric,pp,3.30
copper,L8,1.20,8
dielectric,pp,3.30
copper,L9,1.00,9
dielectric,pp,2.30
copper,L10,0.80,10
soldermask,SM_bot,0.80`;

const DEFAULT_CHANGES = `# 格式：start,end
# 進階：start,end,drill,finish
1,2
2,3
3,4
4,5
5,6`;

const DEFAULT_COORDS = `# 格式：x,y (mil)
0,0`;

export default function App() {
  const [version, setVersion] = useState("2026.1");
  const [material, setMaterial] = useState("copper");
  const [status, setStatus] = useState({ connected: false, text: "尚未連線" });
  
  const [stackup, setStackup] = useState(DEFAULT_STACKUP);
  const [changes, setChanges] = useState(DEFAULT_CHANGES);
  
  const [drill, setDrill] = useState("4.9");
  const [finish, setFinish] = useState("4.0");
  const [autodia, setAutodia] = useState(false);
  
  const [srcMode, setSrcMode] = useState<"grab" | "manual">("grab");
  const [grabMode, setGrabMode] = useState<"selected" | "prefix">("selected");
  const [prefix, setPrefix] = useState("via");
  const [fit, setFit] = useState(true);
  const [replace, setReplace] = useState(false);
  
  const [coords, setCoords] = useState(DEFAULT_COORDS);
  
  const [logs, setLogs] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  
  const [grabbed, setGrabbed] = useState<any[]>([]);
  const [layoutLayerZ, setLayoutLayerZ] = useState<any>({});
  
  const [loading, setLoading] = useState(false);

  // WebSocket for logs
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Using relative path via Vite proxy mapping
    const wsUrl = `${protocol}//${window.location.host}/ws/log`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
      setLogs(prev => [...prev, e.data]);
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Handle connection
  const handleConnect = async () => {
    setLoading(true);
    try {
      const res = await connectAedt(version);
      if (res.status === 'success') {
        setStatus({ connected: true, text: res.message });
      } else {
        setStatus({ connected: false, text: res.message });
      }
    } catch (e: any) {
      setStatus({ connected: false, text: "連線失敗: " + e.message });
    }
    setLoading(false);
  };

  const handleRelease = async () => {
    setLoading(true);
    try {
      const res = await releaseAedt();
      if (res.status === 'success') {
        setStatus({ connected: false, text: res.message });
      } else {
        alert(res.message);
      }
    } catch (e: any) {
      alert("釋放失敗: " + e.message);
    }
    setLoading(false);
  };

  const handleReadStackup = async () => {
    if (!status.connected) return alert("請先連線 AEDT");
    setLoading(true);
    try {
      const res = await readStackup();
      if (res.stackup_text) {
        setStackup(res.stackup_text);
        setLayoutLayerZ(res.layout_layer_z);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAutoChanges = () => {
    const lines = stackup.split('\n');
    const layers = [];
    for (const l of lines) {
      if (l.trim().startsWith('copper')) {
        const p = l.split(',');
        if (p.length >= 4) {
          layers.push(parseInt(p[3]));
        }
      }
    }
    layers.sort((a, b) => a - b);
    if (layers.length < 2) return alert('銅層不足 2 層');
    
    let text = "# 由疊構自動產生\n";
    for (let i = 0; i < layers.length - 1; i++) {
      text += `${layers[i]},${layers[i+1]}\n`;
    }
    setChanges(text);
  };

  const handleGrab = async (mode: 'selected' | 'prefix') => {
    if (!status.connected) return alert("請先連線 AEDT");
    setLoading(true);
    try {
      const res = await grabVias(mode, prefix);
      if (res.status === 'success') {
        setGrabbed(res.grabbed);
        if (autodia && res.grabbed.length > 0) {
          setDrill(res.grabbed[0].dia.toFixed(4));
        }
      } else {
        alert(res.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleBuild = async () => {
    if (!status.connected) return alert("請先連線 AEDT");
    setLoading(true);
    try {
      const payload = {
        stackup,
        changes,
        coords,
        src_mode: srcMode,
        grabbed,
        drill: parseFloat(drill),
        finish: parseFloat(finish),
        autodia,
        fit,
        replace,
        layout_layer_z: layoutLayerZ,
        material
      };
      await buildFunnels(payload);
    } finally {
      setLoading(false);
    }
  };

  // 3D Scene preview derived from current parameters
  const scene = useMemo(() => {
    return buildScene({
      drill: parseFloat(drill) || 0,
      finish: parseFloat(finish) || 0,
      changes
    });
  }, [drill, finish, changes]);

  const fitKey = `${drill}-${finish}-${changes}`;

  return (
    <div className="app-container">
      <div className="header">
        <h1>HFSS 漏斗 Via 網頁建模工具</h1>
        <div className="author">此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供</div>
      </div>
      
      <div className="panel" style={{ marginBottom: 15 }}>
        <div className="row" style={{ alignItems: 'center' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label>AEDT 版本：</label>
            <input type="text" value={version} onChange={e => setVersion(e.target.value)} style={{ width: 60 }} />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label>via 材質：</label>
            <input type="text" value={material} onChange={e => setMaterial(e.target.value)} style={{ width: 80 }} />
          </div>
          <button onClick={handleConnect} disabled={loading || status.connected}>連線 AEDT</button>
          <button className="outline" onClick={handleRelease} disabled={loading || !status.connected}>釋放 AEDT</button>
          <span className={`status-text ${status.connected ? 'success' : 'error'}`}>{status.text}</span>
        </div>
      </div>

      <div className="main-content">
        <div className="left-panel">
          <div className="row">
            <div className="panel col" style={{ display: 'flex', flexDirection: 'column' }}>
              <div className="panel-title">疊構表 STACKUP</div>
              <textarea value={stackup} onChange={e => setStackup(e.target.value)} style={{ flex: 1, minHeight: 200 }} />
              <button className="outline" style={{ marginTop: 10 }} onClick={handleReadStackup} disabled={loading}>⤵ 從 3D Layout 讀取真實疊構</button>
            </div>
            
            <div className="panel col" style={{ display: 'flex', flexDirection: 'column' }}>
              <div className="panel-title">Layer change 表</div>
              <textarea value={changes} onChange={e => setChanges(e.target.value)} style={{ flex: 1, minHeight: 200 }} />
              <button className="outline" style={{ marginTop: 10 }} onClick={handleAutoChanges}>↻ 依疊構自動產生</button>
            </div>
          </div>
          
          <div className="panel">
            <div className="panel-title">Via 來源</div>
            <div className="radio-group">
              <label className="checkbox-label">
                <input type="radio" checked={srcMode === 'grab'} onChange={() => setSrcMode('grab')} /> 抓取 AEDT 物件
              </label>
              <label className="checkbox-label">
                <input type="radio" checked={srcMode === 'manual'} onChange={() => setSrcMode('manual')} /> 手動輸入座標
              </label>
            </div>
            
            {srcMode === 'grab' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="row" style={{ alignItems: 'center' }}>
                  <button onClick={() => handleGrab('selected')} disabled={loading}>① 抓取選取的 via</button>
                  <label className="checkbox-label" style={{ marginLeft: 10 }}>
                    <input type="checkbox" checked={fit} onChange={e => setFit(e.target.checked)} />
                    依 via 頭尾錨定定位節點
                  </label>
                </div>
                <div className="row" style={{ alignItems: 'center' }}>
                  <button onClick={() => handleGrab('prefix')} disabled={loading}>①' 抓取前綴符合的物件</button>
                  <input type="text" value={prefix} onChange={e => setPrefix(e.target.value)} style={{ width: 100, marginLeft: 10 }} placeholder="前綴" />
                </div>
                <div>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={replace} onChange={e => setReplace(e.target.checked)} />
                    取代模式：建立後刪除原本圓柱 via
                  </label>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  已抓取 {grabbed.length} 個物件
                </div>
              </div>
            ) : (
              <div>
                <textarea value={coords} onChange={e => setCoords(e.target.value)} style={{ width: '100%', height: 100 }} />
              </div>
            )}
          </div>
        </div>

        <div className="right-panel">
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="panel-title">Via 寬度與 3D 預覽</div>
            <div className="row" style={{ marginBottom: 15 }}>
              <div className="form-group vertical">
                <label>寬端（上, Drill）：</label>
                <input type="number" step="0.1" value={drill} onChange={e => setDrill(e.target.value)} />
              </div>
              <div className="form-group vertical">
                <label>窄端（下, Finish）：</label>
                <input type="number" step="0.1" value={finish} onChange={e => setFinish(e.target.value)} />
              </div>
            </div>
            <label className="checkbox-label" style={{ marginBottom: 15 }}>
              <input type="checkbox" checked={autodia} onChange={e => {
                setAutodia(e.target.checked);
                if (e.target.checked && grabbed.length > 0) setDrill(grabbed[0].dia.toFixed(4));
              }} />
              寬端＝原選取 via 外徑（自動帶入）
            </label>
            
            <div className="preview-container">
              <Preview3D scene={scene} fitKey={fitKey} />
            </div>
          </div>
        </div>
      </div>
      
      <div className="panel" style={{ marginTop: 15 }}>
        <div className="row" style={{ alignItems: 'center' }}>
          <button style={{ fontSize: 16, padding: '10px 24px', marginRight: 15 }} onClick={handleBuild} disabled={loading}>
            ② 建立漏斗 Via
          </button>
          <div className="log-console" ref={logRef} style={{ flex: 1, height: 100 }}>
            {logs.map((l, i) => <div key={i}>{l}</div>)}
            {logs.length === 0 && <div style={{ color: '#555' }}>執行訊息將顯示於此...</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
