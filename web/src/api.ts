import { Node } from 'reactflow';

class ServerAPI {
    private host: string;
    private mediaHost: string;
    private nodes: any;
    private websocket: WebSocket;
    private listeners: Set<[string, EventListenerOrEventListenerObject]>

    constructor(host: string = 'localhost:8005', mediaHost: string = 'localhost:8006') {
        this.host = host;
        this.mediaHost = mediaHost;
        this.nodes = {};
        this.listeners = new Set();
        this.setupConnection();
        this.connectWebSocket();
    }

    private connectWebSocket() {
        this.websocket = new WebSocket(`ws://${this.host}/ws`);
        for (const [eventType, callback] of this.listeners) {
            this.websocket.addEventListener(eventType, callback);
        }
        this.websocket.onopen = () => {
            console.log("Connected to server.");

        };
        this.websocket.onclose = () => {
            console.log("Lost connection with server. Retrying connection...");
            this.retryWebSocketConnection();
        };
    }

    private retryWebSocketConnection() {
        setTimeout(() => {
            this.connectWebSocket();
        }, 2000);
    }

    public getHost() {
        return this.host;
    }

    public async setHost(host: string) {
        this.host = host;
        this.connectWebSocket();
        await this.setupConnection();
    }

    public getNodeProperties(name: string) {
        return {};
    }

    private async setupConnection() {
        const nodesRes = await this.get('nodes');
        this.nodes = nodesRes;
    }

    public addNodeUpdatedListener(callback: () => void) {
        this.websocket.addEventListener('message', (event) => {
            const message = JSON.parse(event.data);
            if (message.event === 'node_updated') {
                callback();
            }
        });
    }

    private async post(path, data) {
        try {
            const response = await fetch(`http://${this.host}/${path}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            if (response.ok) {
                return await response.json();
            }
        } catch (e) {
            console.error(e);
            return null;
        }
    }

    private async put(path, data) {
        try {
            const response = await fetch(`http://${this.host}/${path}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            if (response.ok) {
                return await response.json();
            }
        } catch (e) {
            console.error(e);
            return null;
        }
    }

    private async get(path) {
        try {
            const response = await fetch(`http://${this.host}/${path}`);
            if (response.ok) {
                return await response.json();
            }
        } catch (e) {
            console.error(e);
            return null;
        }
    }

    public addWsEventListener(eventType: string, callback: EventListenerOrEventListenerObject) {
        this.listeners.add([eventType, callback]);
        this.websocket.addEventListener(eventType, callback);
    }

    public removeWsEventListener(eventType: string, callback: EventListenerOrEventListenerObject) {
        this.listeners.delete([eventType, callback]);
        this.websocket.removeEventListener(eventType, callback);
    }

    public addWSMessageListener(callback: EventListenerOrEventListenerObject) {
        this.addWsEventListener('message', callback);
    }

    public removeWSMessageListener(callback: EventListenerOrEventListenerObject) {
        this.removeWsEventListener('message', callback);
    }

    /**
     * Processor API
     */
    public async runAll(graph, resources) {
        console.log(graph, resources)
        return await this.post('run', { graph, resources });
    }

    public async run(graph, resources, stepId) {
        return await this.post(`run/${stepId}`, { graph, resources });
    }

    public async step(graph, resources, stepId) {
        return await this.post(`step/${stepId}`, { graph, resources });
    }

    public async pause() {
        return await this.post('pause', {});
    }

    public async clearAll(graph, resources) {
        console.log("Clearing all")
        return await this.post('clear', { graph, resources });
    }

    public async clear(graph, resources, stepId) {
        return await this.post(`clear/${stepId}`, { graph, resources });
    }

    public async getNodes() {
        return await this.get('nodes');
    }

    /**
     * File API
     */
    public async listFiles() {
        const workflowFiles = await this.get('fs?stat=true');
        return workflowFiles.children;
    }

    public async putItem(filepath, isFile, content = null, hash_key = null) {
        return await this.put(`fs/${filepath}`, {
            is_file: isFile,
            file_contents: content ?? '',
            hash_key: hash_key ?? ''
        });
    }

    public async getFile(filepath) {
        return await this.get(`fs/${filepath}`);
    }

    /**
     * Graph API
     */
    public putNode(node: Node) {
        this.websocket.send(JSON.stringify({
            api: "graph",
            cmd: "put_node",
            node: node
        }));
    }

    /**
     * Image API
     */
    public getImagePath(imageName: string) {
        return `http://${this.mediaHost}/${imageName}`;
    }
}

export const API = new ServerAPI();
