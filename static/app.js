let currentLogServer = null;

async function fetchServers() {
    const res = await fetch("/api/servers");
    const data = await res.json();
    const tbody = document.querySelector("#servers-table tbody");
    tbody.innerHTML = "";
    data.forEach(s => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${s.name}</td>
            <td>${s.type}</td>
            <td>${s.status}</td>
            <td>${s.cpu.toFixed(1)}</td>
            <td>${s.memory.toFixed(1)}</td>
            <td>
                <input type="checkbox" ${s.monitoring?"checked":""} onchange="toggleMonitor('${s.name}',this.checked)">
            </td>
            <td>
                <button onclick="startServer('${s.name}')">Start</button>
                <button onclick="stopServer('${s.name}')">Stop</button>
                <button onclick="restartServer('${s.name}')">Restart</button>
                <button onclick="viewLog('${s.name}')">View Log</button>
                <button onclick="deleteServer('${s.name}')">Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function startServer(name){ await fetch(`/api/servers/${name}/start`,{method:"POST"}); fetchServers();}
async function stopServer(name){ await fetch(`/api/servers/${name}/stop`,{method:"POST"}); fetchServers();}
async function restartServer(name){ await fetch(`/api/servers/${name}/restart`,{method:"POST"}); fetchServers();}
async function toggleMonitor(name,state){ await fetch(`/api/servers/${name}/monitor`,{method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({state:state?"on":"off"})}); fetchServers();}
async function createServer(){
    const name=document.getElementById("new-server-name").value;
    const type=document.getElementById("new-server-type").value;
    if(!name) return alert("Enter a name");
    await fetch("/api/servers",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,type})});
    fetchServers();
}
async function deleteServer(name){ if(confirm(`Delete ${name}?`)){ await fetch(`/api/servers/${name}`,{method:"DELETE"}); fetchServers(); }}
async function viewLog(name){ currentLogServer=name; document.getElementById("log-server-name").innerText=name; fetchLog(); }

async function sendInput(){
    const input=document.getElementById("log-input").value;
    if(!currentLogServer) return alert("Select a server log first");
    await fetch(`/api/servers/${currentLogServer}/send`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:input})});
    document.getElementById("log-input").value="";
}

async function fetchLog(){
    if(!currentLogServer) return;
    const res=await fetch(`/api/servers/${currentLogServer}/log`);
    const data=await res.json();
    document.getElementById("log-content").innerText=data.log.join("");
    setTimeout(fetchLog,1000);
}

fetchServers();
setInterval(fetchServers,2000);
