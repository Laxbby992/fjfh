import websockets
import asyncio
import random
import base64
import httpx
import json
import time
import sys
import re
import logging
import string
from flask import Flask, render_template_string, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KahootClient():
    def __init__(self):
        pass

    async def join(self, game_pin, nick):
        sessionRequest = httpx.get(f'https://kahoot.it/reserve/session/{game_pin}/?{int(time.time() * 1000)}')
        sessionToken = sessionRequest.headers['x-kahoot-session-token']
        sessionChallenge = sessionRequest.json()['challenge'].replace(' ', '').replace('    ', '').replace(' ', '')

        def getMessage(input_string):
            message_match = re.search(r"decode\.call\(this,'(.*?)'", input_string)
            if message_match:
                message = message_match.group(1)
            else:
                raise ValueError("Message not found in input string")
            return message

        def getOffset(input_string):
            message_match = re.search(r"decode\.call\(this,'(.*?)'", input_string)
            if message_match:
                message = message_match.group(1)
            else:
                raise ValueError("Message not found in input string")
            offset_match = re.search(r'offset\s*=\s*(.*?);', input_string)
            if offset_match:
                offset_expr = offset_match.group(1)
            else:
                raise ValueError("Offset calculation not found in input string")
            try:
                offset = eval(offset_expr)
            except Exception as e:
                raise ValueError(f"Failed to evaluate offset expression: {e}")
            return offset

        def xor_string(e, t):
            o = ""
            for r in range(len(e)):
                n = ord(e[r])
                s = ord(t[r % len(t)])
                a = n ^ s
                o += chr(a)
            return o

        def decode_session_token(e, message, offset_equation):
            r = ''.join(chr((ord(char) * position + eval(str(offset_equation))) % 77 + 48) for position, char in enumerate(getMessage(message)))
            n = base64.b64decode(e).decode('utf-8')
            return xor_string(n, r)

        connToken = decode_session_token(sessionToken, sessionChallenge, getOffset(sessionChallenge))
        logging.info(f"Attempting to join game {game_pin} as {nick}")

        try:
            async with websockets.connect(f"wss://kahoot.it/cometd/{game_pin}/{connToken}") as websocket:
                requestId = 1
                handshake_data = {
                    "id": str(requestId),
                    "version": "1.0",
                    "minimumVersion": "1.0",
                    "channel": "/meta/handshake",
                    "supportedConnectionTypes": ["websocket"],
                    "advice": {
                        "timeout": 60000,
                        "interval": 0
                    },
                    "ext": {
                        "ack": True,
                        "timesync": {
                            "tc": int(time.time() * 1000),
                            "l": 0,
                            "o": 0
                        }
                    }
                }
                await websocket.send(json.dumps([handshake_data]))
                response = await websocket.recv()
                clientId = json.loads(response)[0]['clientId']
                requestId += 1
                connect_data = {
                    "id": str(requestId),
                    "channel": "/meta/connect",
                    "connectionType": "websocket",
                    "advice": {"timeout": 0},
                    "clientId": clientId,
                    "ext": {
                        "ack": 0,
                        "timesync": {
                            "tc": int(time.time() * 1000),
                            "l": 0,
                            "o": 0
                        }
                    }
                }
                await websocket.send(json.dumps([connect_data]))
                requestId += 1
                response = await websocket.recv()
                device_info = {
                    "device": {
                        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/533.36",
                        "screen": {
                            "width": 1920,
                            "height": 1080
                        }
                    }
                }
                login_data = {
                    "id": str(requestId),
                    "channel": "/service/controller",
                    "data": {
                        "type": "login",
                        "gameid": str(game_pin),
                        "host": "kahoot.it",
                        "name": f"{nick}",
                        "content": json.dumps(device_info)
                    },
                    "clientId": clientId,
                    "ext": {}
                }
                await websocket.send(json.dumps([login_data]))
                requestId += 1
                login_data = [
                    {
                        "id": str(requestId),
                        "channel": "/meta/connect",
                        "connectionType": "websocket",
                        "clientId": clientId,
                        "ext": {
                            "ack": 1,
                            "timesync": {
                                "tc": int(time.time() * 1000),
                                "l": 0,
                                "o": 0
                            }
                        }
                    }
                ]
                await websocket.send(json.dumps(login_data))
                requestId += 1
                response = await websocket.recv()
                message_data = {
                    "id": str(requestId),
                    "channel": "/service/controller",
                    "data": {
                        "gameid": str(game_pin),
                        "type": "message",
                        "host": "kahoot.it",
                        "id": 16,
                        "content": json.dumps({"usingNamerator": False})
                    },
                    "clientId": clientId,
                    "ext": {}
                }
                await websocket.send(json.dumps([message_data]))
                requestId += 1
                response = await websocket.recv()
                connect_ack_data = {
                    "id": str(requestId),
                    "channel": "/meta/connect",
                    "connectionType": "websocket",
                    "clientId": clientId,
                    "ext": {
                        "ack": 2,
                        "timesync": {
                            "tc": int(time.time() * 1000),
                            "l": 0,
                            "o": 0
                        }
                    }
                }
                await websocket.send(json.dumps([connect_ack_data]))
                requestId += 1
                connect_ack_data2 = {
                    "id": str(requestId),
                    "channel": "/service/controller",
                    "data": {
                        "gameid": game_pin,
                        "type": "message",
                        "host": "kahoot.it",
                        "id": 61,
                        "content": "{\"points\":0}"
                    },
                    "clientId": clientId,
                    "ext": {}
                }
                await websocket.send(json.dumps([connect_ack_data2]))
                requestId += 1
                current_ack = 1
                async def send_heartbeat():
                    nonlocal current_ack
                    while True:
                        heartbeat_data = {
                            "id": str(requestId),
                            "channel": "/meta/connect",
                            "connectionType": "websocket",
                            "clientId": clientId,
                            "ext": {
                                "ack": current_ack,
                                "timesync": {
                                    "tc": int(time.time() * 1000),
                                    "l": 0,
                                    "o": 0
                                }
                            }
                        }
                        try:
                           await websocket.send(json.dumps([heartbeat_data]))
                           current_ack += 1
                           await asyncio.sleep(10)
                        except websockets.ConnectionClosed:
                            break
                        except Exception as e:
                            break
                heartbeat_task = asyncio.create_task(send_heartbeat())
                while True:
                    try:
                        response = await websocket.recv()
                    except websockets.ConnectionClosed:
                        break
                    except Exception as e:
                        break
        except websockets.ConnectionClosedError as e:
            logging.error(f"Connection closed for {nick}: {e}")
            raise e
        except Exception as e:
            logging.error(f"Error joining as {nick}: {e}")
            raise e

app = Flask(__name__)

def generate_random_suffix(length=4):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EzFlooder</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&display=swap" rel="stylesheet"/>
  <style>
    body {
      margin: 0;
      font-family: 'Poppins', sans-serif;
      background: #0d1117;
      color: white;
      overflow-x: hidden;
    }
    canvas#bg {
      position: fixed;
      top: 0;
      left: 0;
      z-index: -1;
    }
    .container {
      max-width: 800px;
      margin: auto;
      padding: 2rem;
    }
    h1 {
      text-align: center;
      font-size: 2rem;
      margin-bottom: 1rem;
    }
    form {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .form-group, .checkbox-group {
      display: flex;
      flex-direction: column;
    }
    label {
      margin-bottom: 0.3rem;
      font-weight: 500;
    }
    input[type="text"], input[type="number"] {
      padding: 0.5rem 1rem;
      border: none;
      border-radius: 12px;
      font-size: 1rem;
      font-family: 'Poppins', sans-serif;
    }
    .checkbox-group {
      flex-direction: row;
      align-items: center;
      gap: 0.5rem;
    }
    button {
      background: linear-gradient(135deg, #00ffff, #0066ff);
      color: black;
      font-family: 'Poppins', sans-serif;
      padding: 0.5rem 1rem;
      border: none;
      border-radius: 12px;
      font-size: 1rem;
      cursor: pointer;
      transition: all 0.3s ease;
    }
    button:hover {
      opacity: 0.8;
    }
    .progress-container {
      width: 100%;
      background: #333;
      border-radius: 12px;
      overflow: hidden;
      margin-top: 1rem;
      display: none;
    }
    .progress-bar {
      height: 20px;
      width: 0%;
      background: linear-gradient(135deg, #00ffff, #0066ff);
      transition: width 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .progress-bar-text {
      font-size: 0.9rem;
      color: black;
      font-weight: bold;
    }
    .success-color {
      background: #00e676 !important;
    }
    .error-color {
      background: #ff1744 !important;
    }
    #statusMessage {
      margin-top: 1rem;
      font-size: 1rem;
      text-align: center;
    }
    .loading-dots span {
      display: inline-block;
      width: 8px;
      height: 8px;
      margin: 0 2px;
      background: white;
      border-radius: 50%;
      animation: loading 1s infinite ease-in-out;
    }
    .loading-dots span:nth-child(2) {
      animation-delay: 0.2s;
    }
    .loading-dots span:nth-child(3) {
      animation-delay: 0.4s;
    }
    @keyframes loading {
      0%, 80%, 100% {
        transform: scale(0);
      }
      40% {
        transform: scale(1);
      }
    }
    .footer {
      text-align: center;
      margin-top: 4rem;
      padding-bottom: 1rem;
      color: #888;
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
  <h1>EzFlooder</h1>
  <form id="floodForm">
    <div class="form-group">
      <label for="gamePin">Game PIN:</label>
      <input type="text" id="gamePin" name="gamePin" required>
    </div>
    <div class="form-group">
      <label for="numBots">Number of Bots:</label>
      <input type="number" id="numBots" name="numBots" min="1" value="1" required>
    </div>
    <div class="form-group">
      <label for="customName">Custom Bot Name (Optional):</label>
      <input type="text" id="customName" name="customName">
    </div>
    <div class="checkbox-group">
      <input type="checkbox" id="addRandom" name="addRandom" checked>
      <label for="addRandom">Add Random String (e.g. _aBcD)</label>
    </div>
    <button type="submit" id="floodButton">Start Flooding</button>
  </form>
  <div class="progress-container" id="progressBarContainer">
    <div class="progress-bar" id="progressBar">
      <span class="progress-bar-text" id="progressBarText">0%</span>
    </div>
  </div>
  <div id="statusMessage"></div>
  <div class="footer">&copy; EzFlooder (Made by Laxbby99) 2025. All rights reserved.</div>
</div>

<script>
  const canvas = document.getElementById('bg');
  const ctx = canvas.getContext('2d');
  let w = canvas.width = window.innerWidth;
  let h = canvas.height = window.innerHeight;
  let particles = Array.from({length: 60}, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: Math.random() * 2 + 1,
    dx: (Math.random() - 0.5) * 0.5,
    dy: (Math.random() - 0.5) * 0.5
  }));

  function animate() {
    ctx.clearRect(0, 0, w, h);
    for (let p of particles) {
      ctx.beginPath();
      const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
      gradient.addColorStop(0, 'cyan');
      gradient.addColorStop(1, 'blue');
      ctx.fillStyle = gradient;
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
      p.x += p.dx;
      p.y += p.dy;
      if (p.x < 0 || p.x > w) p.dx *= -1;
      if (p.y < 0 || p.y > h) p.dy *= -1;
    }
    requestAnimationFrame(animate);
  }
  animate();
  window.onresize = () => {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  };

  const form = document.getElementById('floodForm');
  const floodButton = document.getElementById('floodButton');
  const statusMessageDiv = document.getElementById('statusMessage');
  const progressBarContainer = document.getElementById('progressBarContainer');
  const progressBar = document.getElementById('progressBar');
  const progressBarText = document.getElementById('progressBarText');
  let progressInterval = null;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const gamePin = document.getElementById('gamePin').value;
    const numBots = parseInt(document.getElementById('numBots').value, 10);
    const customName = document.getElementById('customName').value;
    const addRandom = document.getElementById('addRandom').checked;

    if (!gamePin || numBots <= 0) {
      statusMessageDiv.innerHTML = '<span style="color: #ffcc80;">Please enter valid Game PIN and Number of Bots.</span>';
      return;
    }

    floodButton.disabled = true;
    statusMessageDiv.innerHTML = 'Starting flood... <div class="loading-dots"><span></span><span></span><span></span></div>';
    progressBarContainer.style.display = 'block';
    progressBar.style.width = '0%';
    progressBarText.innerText = '0%';
    progressBar.classList.remove('success-color', 'error-color');
    progressBar.style.background = '';

    let progress = 0;
    const intervalTime = 50;
    const totalTime = 3000;
    const increment = (intervalTime / totalTime) * 95;

    if (progressInterval) clearInterval(progressInterval);

    progressInterval = setInterval(() => {
      if (progress < 95) {
        progress += increment;
        if (progress > 95) progress = 95;
        const displayProgress = Math.round(progress);
        progressBar.style.width = displayProgress + '%';
        progressBarText.innerText = displayProgress + '%';
      } else {
        clearInterval(progressInterval);
      }
    }, intervalTime);

    try {
      const response = await fetch('/flood', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          gamePin, numBots, customName, addRandom: addRandom ? 'true' : 'false'
        })
      });

      clearInterval(progressInterval);
      progressInterval = null;

      const result = await response.json();
      progressBar.style.width = '100%';

      if (response.ok) {
        statusMessageDiv.innerHTML = `<span style="color: #a5d6a7;">${result.message}</span>`;
        progressBarText.innerText = '100%';
        progressBar.classList.add('success-color');
        progressBar.style.background = '';
      } else {
        statusMessageDiv.innerHTML = `<span style="color: #ef9a9a;">Error: ${result.error}</span>`;
        progressBarText.innerText = 'Error';
        progressBar.classList.add('error-color');
        progressBar.style.background = '';
      }

    } catch (error) {
      if (progressInterval) clearInterval(progressInterval);
      progressInterval = null;
      progressBar.style.width = '100%';
      progressBar.classList.add('error-color');
      progressBar.style.background = '';
      progressBarText.innerText = 'Error';
      statusMessageDiv.innerHTML = `<span style="color: #ef9a9a;">An error occurred: ${error.message}</span>`;
    } finally {
      floodButton.disabled = false;
      setTimeout(() => {
        progressBarContainer.style.display = 'none';
        progressBar.style.width = '0%';
        progressBarText.innerText = '0%';
        progressBar.classList.remove('success-color', 'error-color');
        progressBar.style.background = '';
      }, 4000);
    }
  });
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/flood', methods=['POST'])
def flood():
    game_pin = request.form.get('gamePin')
    num_bots = request.form.get('numBots', type=int)
    custom_name = request.form.get('customName', '').strip()
    add_random = request.form.get('addRandom') == 'true'

    if not game_pin or not num_bots or num_bots <= 0:
        logging.warning("Invalid request: Missing PIN osonify({"error": "Invalid game PIN or number of bots."}), 400

    async def run_flood_tasks(pin, count, base_name, use_random_suffix):
        client = KahootClient()
        tasks = []
        logging.info(f"Starting flood of {count} bots to game {pin}")
        for i in range(count):
            name = base_name if base_name else "Bot"
            suffix = f"_{i+1}" if not base_name else ""
            if use_random_suffix:
                random_suffix = generate_random_suffix(random.randint(3, 6))
                name = f"{name}{suffix}_{random_suffix}" if suffix else f"{name}_{random_suffix}"
            elif not base_name:
                 name = f"{name}_{i+1}"
            
            # Limiting name length based on potential Kahoot limits
            max_kahoot_name_length = 15 
            if len(name) > max_kahoot_name_length:
                 name = name[:max_kahoot_name_length]


            tasks.append(client.join(pin, name))
            await asyncio.sleep(0.2) # Keep a small delay

        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful_joins = sum(1 for res in results if not isinstance(res, Exception))
        failed_joins = count - successful_joins
        
        log_message = f"Flood attempt finished for game {pin}. Successfully initiated connections for {successful_joins}/{count} bots."
        if failed_joins > 0:
            log_message += f" Failed attempts: {failed_joins}."
            # Log first few specific errors if needed
            errors_logged = 0
            for i, res in enumerate(results):
                if isinstance(res, Exception) and errors_logged < 3:
                     logging.warning(f"Bot {i+1} failed: {res}")
                     errors_logged += 1

        logging.info(log_message)
        # The message returned to the user remains general
        return f"Flood attempt finished. Initiated {successful_joins}/{count} bot connections."


    try:
        # Running asyncio task properly
        message = asyncio.run(run_flood_tasks(game_pin, num_bots, custom_name, add_random))
        return jsonify({"message": message})
    except Exception as e:
        logging.error(f"An error occurred during flood orchestration: {e}")
        return jsonify({"error": f"Server error during flood setup: {e}"}), 500

if __name__ == '__main__':
     app.run(host='0.0.0.0', port=5000, debug=False)
