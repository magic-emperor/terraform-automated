<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const tfDir = ref('')
const destroyHours = ref(4)
const sessionId = ref(null)
const status = ref('Idle')
const destroyAt = ref(null)
const logs = ref([])
const errorMsg = ref('')

const ws = ref(null)
const countdownTimer = ref(null)
const timeRemaining = ref('')

const connectWebSocket = () => {
  ws.value = new WebSocket('ws://localhost:8000/ws')
  ws.value.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'log') {
      if (data.session_id === sessionId.value) {
        logs.value.push({
          id: Date.now() + Math.random(),
          stage: data.stage,
          stream: data.stream,
          text: data.text
        })
        setTimeout(() => {
          const el = document.getElementById('log-container')
          if (el) el.scrollTop = el.scrollHeight
        }, 50)
      }
    } else if (data.type === 'status_update') {
      if (data.session_id === sessionId.value) {
        if(data.status) status.value = data.status
        if (data.destroy_at) {
          destroyAt.value = new Date(data.destroy_at)
        }
        if (data.error) {
          errorMsg.value = data.error
        }
      }
    } else if (data.type === 'stage_update') {
      if (data.session_id === sessionId.value) {
        status.value = data.stage
      }
    }
  }
  ws.value.onclose = () => {
      setTimeout(connectWebSocket, 3000)
  }
}

const updateCountdown = () => {
  if (!destroyAt.value || status.value !== 'Active') {
    timeRemaining.value = ''
    return
  }
  const now = new Date()
  const diff = destroyAt.value - now
  if (diff <= 0) {
    timeRemaining.value = '00:00:00'
    return
  }
  
  const h = Math.floor(diff / (1000 * 60 * 60))
  const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  const s = Math.floor((diff % (1000 * 60)) / 1000)
  timeRemaining.value = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

onMounted(() => {
  connectWebSocket()
  countdownTimer.value = setInterval(updateCountdown, 1000)
})

onUnmounted(() => {
  if (ws.value) ws.value.close()
  clearInterval(countdownTimer.value)
})

const deploy = async () => {
  if (!tfDir.value) {
    errorMsg.value = "Please provide the Terraform directory."
    return
  }
  errorMsg.value = ""
  logs.value = []
  
  try {
    const res = await fetch('http://localhost:8000/api/terraform/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tf_dir: tfDir.value,
        destroy_time_hours: parseFloat(destroyHours.value)
      })
    })
    const data = await res.json()
    if (data.error) {
      errorMsg.value = data.error
    } else {
      sessionId.value = data.session_id
      status.value = 'Scheduled'
    }
  } catch (err) {
    errorMsg.value = "Failed to connect to backend."
  }
}

const forceDestroy = async () => {
  if (!sessionId.value) return
  
  try {
    const res = await fetch(`http://localhost:8000/api/terraform/destroy/${sessionId.value}`, {
      method: 'POST'
    })
    const data = await res.json()
    if (data.error) {
      errorMsg.value = data.error
    }
  } catch(err) {
    errorMsg.value = "Failed to send destroy command."
  }
}
</script>

<template>
  <div class="app-wrapper">
    <div class="glass-panel main-panel">
      <header>
        <h1>Terraform <span class="accent">Manager</span></h1>
        <div class="status-badge" :class="status.toLowerCase().replace(' ', '-')">
          <span class="pulse-dot"></span>
          {{ status }}
        </div>
      </header>

      <div class="error-msg" v-if="errorMsg">{{ errorMsg }}</div>

      <div class="controls-grid" v-if="!sessionId || status === 'Idle' || status.includes('Failed') || status === 'Destroyed'">
        <div class="input-group">
          <label>Terraform Directory Path</label>
          <input type="text" v-model="tfDir" placeholder="e.g. C:/Projects/my-infrastructure" />
        </div>
        
        <div class="input-group">
          <label>Auto-Destroy After (Hours)</label>
          <input type="number" v-model="destroyHours" step="0.5" min="0.1" />
        </div>

        <button class="btn-primary" @click="deploy">
          Initialize & Deploy
        </button>
      </div>

      <div class="active-dashboard" v-else>
        <div class="timer-section" v-if="status === 'Active'">
          <h2>Destruction Countdown</h2>
          <div class="timer">{{ timeRemaining }}</div>
          <button class="btn-danger" @click="forceDestroy">
            Destroy Now
          </button>
        </div>

        <div class="logs-section">
          <div class="logs-header">Execution Logs</div>
          <div class="log-container" id="log-container">
            <div v-for="log in logs" :key="log.id" class="log-line" :class="log.stream">
              <span class="log-stage">[{{ log.stage }}]</span> {{ log.text }}
            </div>
            <div v-if="logs.length === 0" class="empty-logs">Waiting for output...</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-wrapper {
  padding: 2rem;
  width: 100%;
  max-width: 1000px;
  margin: 0 auto;
}

.glass-panel {
  background: rgba(30, 30, 35, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 2.5rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 1.5rem;
}

h1 {
  margin: 0;
  font-size: 2.2rem;
  font-weight: 700;
  color: #fff;
}

.accent {
  background: -webkit-linear-gradient(45deg, #00f2fe, #4facfe);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 50px;
  font-weight: 600;
  font-size: 0.9rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #aaa;
}

.status-badge.active .pulse-dot { background: #42d392; box-shadow: 0 0 10px #42d392; }
.status-badge.deploying .pulse-dot, .status-badge.initializing .pulse-dot, .status-badge.planning .pulse-dot, .status-badge.applying .pulse-dot { background: #4facfe; box-shadow: 0 0 10px #4facfe; animation: pulse 1s infinite alternate; }
.status-badge.destroying .pulse-dot { background: #ff4b4b; animation: pulse 1s infinite alternate; }

@keyframes pulse {
  from { opacity: 0.5; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1.2); }
}

.controls-grid {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  text-align: left;
}

.input-group label {
  font-size: 0.9rem;
  color: #aaa;
  font-weight: 500;
}

input {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 1rem;
  border-radius: 10px;
  color: white;
  font-family: inherit;
  font-size: 1rem;
  transition: all 0.3s ease;
}

input:focus {
  outline: none;
  border-color: #4facfe;
  box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.2);
}

button {
  cursor: pointer;
  padding: 1rem 2rem;
  border-radius: 10px;
  border: none;
  font-weight: 600;
  font-size: 1.1rem;
  transition: all 0.3s ease;
  font-family: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.btn-primary {
  background: linear-gradient(45deg, #00f2fe, #4facfe);
  color: white;
  margin-top: 1rem;
  box-shadow: 0 10px 20px -10px rgba(79, 172, 254, 0.5);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 15px 25px -10px rgba(79, 172, 254, 0.6);
}

.active-dashboard {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.timer-section {
  text-align: center;
  padding: 2rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 15px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.timer {
  font-size: 4rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  background: -webkit-linear-gradient(45deg, #ff4b4b, #ff9068);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 1rem 0;
  text-shadow: 0 0 20px rgba(255, 75, 75, 0.2);
}

.btn-danger {
  background: rgba(255, 75, 75, 0.1);
  color: #ff4b4b;
  border: 1px solid rgba(255, 75, 75, 0.3);
  margin: 0 auto;
}

.btn-danger:hover {
  background: #ff4b4b;
  color: white;
}

.logs-section {
  display: flex;
  flex-direction: column;
  height: 400px;
  background: #0f0f11;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.logs-header {
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  color: #aaa;
}

.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  font-family: 'Fira Code', monospace, Consolas;
  font-size: 0.9rem;
  line-height: 1.4;
  text-align: left;
}

.log-line {
  margin-bottom: 0.2rem;
  word-break: break-all;
}

.log-line.stderr {
  color: #ff6b6b;
}

.log-stage {
  color: #4facfe;
  font-weight: bold;
}

.empty-logs {
  color: #666;
  font-style: italic;
  text-align: center;
  margin-top: 2rem;
}

.error-msg {
  background: rgba(255, 75, 75, 0.1);
  border-left: 4px solid #ff4b4b;
  padding: 1rem;
  margin-bottom: 1.5rem;
  border-radius: 4px;
  color: #ffbaba;
  text-align: left;
}
</style>
