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
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EzFlooder</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {
            box-sizing: border-box;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            background-size: 400% 400%;
            animation: gradientAnimation 15s ease infinite;
            color: #fff;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }

        @keyframes gradientAnimation {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .container {
            background-color: rgba(0, 0, 0, 0.2);
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.18);
            text-align: center;
            max-width: 450px;
            width: 100%;
            animation: scaleIn 0.6s ease-out;
            position: relative;
            overflow: hidden;
        }

        @keyframes scaleIn {
            from { opacity: 0; transform: scale(0.9); }
            to { opacity: 1; transform: scale(1); }
        }

        h1 {
            margin-bottom: 30px;
            color: #fff;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
            font-size: 2.2rem;
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.95rem;
        }

        input[type="text"],
        input[type="number"] {
            width: 100%;
            padding: 12px 18px;
            border: none;
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 1rem;
            font-family: 'Poppins', sans-serif;
            transition: background-color 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        input[type="text"]::placeholder,
        input[type="number"]::placeholder {
            color: rgba(255, 255, 255, 0.5);
        }

        input[type="text"]:focus,
        input[type="number"]:focus {
            outline: none;
            background-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 0 3px rgba(77, 208, 225, 0.4); /* Cyan focus */
            border-color: rgba(77, 208, 225, 0.6);
        }

        .checkbox-group {
            display: flex;
            align-items: center;
            margin-top: -10px;
            margin-bottom: 20px;
        }

        .checkbox-group input[type="checkbox"] {
            margin-right: 10px;
            width: 18px;
            height: 18px;
            accent-color: #00bcd4; /* Cyan */
            cursor: pointer;
        }

        .checkbox-group label {
            margin-bottom: 0;
            font-weight: 400;
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.8);
            cursor: pointer;
        }


        button {
            background: linear-gradient(45deg, #00bcd4 0%, #4dd0e1 100%); /* Cyan gradient */
            color: white;
            padding: 14px 25px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1.1rem;
            font-weight: 700;
            font-family: 'Poppins', sans-serif;
            transition: opacity 0.3s ease, transform 0.1s ease, background-color 0.3s ease, box-shadow 0.3s ease;
            width: 100%;
            margin-top: 15px;
            box-shadow: 0 4px 15px rgba(0, 188, 212, 0.3);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        button:hover {
            opacity: 0.9;
            box-shadow: 0 6px 20px rgba(0, 188, 212, 0.4);
        }

        button:active {
            transform: scale(0.98);
            box-shadow: 0 2px 10px rgba(0, 188, 212, 0.3);
        }

        button:disabled {
            background: #90a4ae; /* Greyer disabled state */
            cursor: not-allowed;
            box-shadow: none;
            opacity: 0.7;
        }

        .progress-container {
            width: 100%;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            margin-top: 25px;
            overflow: hidden;
            height: 22px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            display: none;
        }

        .progress-bar {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #00bcd4, #80deea); /* Lighter cyan gradient */
            border-radius: 10px; /* Adjusted for container */
            transition: width 0.4s ease-in-out, background-color 0.4s ease;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .progress-bar-text {
            position: absolute; /* Keep absolute for fine control if needed */
            width: 100%;
            text-align: center;
            color: white;
            font-weight: bold;
            font-size: 0.8rem;
            line-height: 22px; /* Match container height */
            text-shadow: 1px 1px 1px rgba(0, 0, 0, 0.6);
            z-index: 2;
            transition: color 0.4s ease;
        }

        #statusMessage {
            margin-top: 15px;
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.9);
            min-height: 1.5em;
            word-break: break-word;
        }

        .loading-dots {
            display: inline-block;
            position: relative;
            width: 60px;
            text-align: center;
            margin-left: 10px;
            vertical-align: middle;
        }

        .loading-dots span {
            position: relative;
            width: 8px;
            height: 8px;
            margin: 0 2px;
            background-color: #fff;
            border-radius: 50%;
            display: inline-block;
            animation: dot-animation 1.4s infinite ease-in-out both;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
        .loading-dots span:nth-child(3) { animation-delay: 0s; }

        @keyframes dot-animation {
            0%, 80%, 100% { transform: scale(0); opacity: 0; }
            40% { transform: scale(1); opacity: 1; }
        }

        .footer {
            margin-top: 30px;
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.5);
        }

        .success-color { background: linear-gradient(90deg, #4CAF50, #8bc34a); }
        .error-color { background: linear-gradient(90deg, #f44336, #ef5350); }

    </style>
</head>
<body>
    <div class="container">
        <h1>EzFlooder</h1>
        <form id="floodForm">
            <div class="form-group">
                <label for="delay">Game PIN:</label>
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
            <div class="form-group">
                <label for="gamePin">Join Delay:</label>
                <input type="number" id="delay" name="delay" required>
            </div>
            <button type="submit" id="floodButton">Start Flooding</button>
        </form>
        <div class="progress-container" id="progressBarContainer">
            <div class="progress-bar" id="progressBar">
                 <span class="progress-bar-text" id="progressBarText">0%</span>
            </div>
        </div>
        <div id="statusMessage"></div>
         <div class="footer">
            &copy; EzFlooder (Made by Laxbby99) 2025. All rights reserved.
        </div>
    </div>

    <script>
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
                 statusMessageDiv.innerHTML = '<span style="color: #ffcc80;">Please enter valid Game PIN and Number of Bots.</span>'; // Warning color
                 return;
            }

            floodButton.disabled = true;
            statusMessageDiv.innerHTML = 'Starting flood... <div class="loading-dots"><span></span><span></span><span></span></div>';
            progressBarContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressBarText.innerText = '0%';
            progressBar.classList.remove('success-color', 'error-color'); // Reset colors
            progressBar.style.background = ''; // Reset to default gradient

            let progress = 0;
            const intervalTime = 50;
            const totalTime = 3000;
            const increment = (intervalTime / totalTime) * 95; // Animate up to 95% cosmetically

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
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        gamePin: gamePin,
                        numBots: numBots,
                        customName: customName,
                        addRandom: addRandom ? 'true' : 'false'
                    })
                });

                clearInterval(progressInterval);
                progressInterval = null;

                const result = await response.json();

                progressBar.style.width = '100%'; // Go to 100%

                if (response.ok) {
                    statusMessageDiv.innerHTML = `<span style="color: #a5d6a7;">${result.message}</span>`; // Success color
                    progressBarText.innerText = '100%';
                    progressBar.classList.add('success-color');
                    progressBar.style.background = ''; // Override inline style if set
                } else {
                    statusMessageDiv.innerHTML = `<span style="color: #ef9a9a;">Error: ${result.error}</span>`; // Error color
                    progressBarText.innerText = 'Error';
                    progressBar.classList.add('error-color');
                    progressBar.style.background = ''; // Override inline style if set
                }

            } catch (error) {
                 if (progressInterval) clearInterval(progressInterval);
                 progressInterval = null;
                 progressBar.style.width = '100%'; // Show full bar on error
                 progressBar.classList.add('error-color');
                 progressBar.style.background = ''; // Override inline style if set
                 progressBarText.innerText = 'Error';
                 statusMessageDiv.innerHTML = `<span style="color: #ef9a9a;">An error occurred: ${error.message}</span>`;
            } finally {
                floodButton.disabled = false;
                 setTimeout(() => {
                    progressBarContainer.style.display = 'none';
                    progressBar.style.width = '0%';
                    progressBarText.innerText = '0%';
                    progressBar.classList.remove('success-color', 'error-color');
                    progressBar.style.background = ''; // Reset background fully
                 }, 4000); // Increased delay to see final state
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
    delay = request.form.get('delay')
    game_pin = request.form.get('gamePin')
    num_bots = request.form.get('numBots', type=int)
    custom_name = request.form.get('customName', '').strip()
    add_random = request.form.get('addRandom') == 'true'

    if not game_pin or not num_bots or num_bots <= 0:
        logging.warning("Invalid request: Missing PIN or bot count.")
        return jsonify({"error": "Invalid game PIN or number of bots."}), 400

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
            await asyncio.sleep(delay) # Keep a small delay

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
