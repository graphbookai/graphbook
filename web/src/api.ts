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
    }

    public connect(host: string, mediaHost: string) {
        this.host = host;
        this.mediaHost = mediaHost;
        this.connectWebSocket();
    }

    public disconnect() {
        if (this.websocket) {
            this.websocket.close();
        }
    }

    private connectWebSocket() {
        this.websocket = new WebSocket(`ws://${this.host}/ws`);
        for (const [eventType, callback] of this.listeners) {
            this.websocket.addEventListener(eventType, callback);
        }
        this.websocket.onopen = () => {
            console.log("Connected to server.");
            this.refreshNodeCatalogue();
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

    public getMediaHost() {
        return this.mediaHost;
    }

    public setHost(host: string) {
        this.host = host;
        this.connectWebSocket();
    }

    public setMediaHost(host: string) {
        this.mediaHost = host;
    }

    public getNodeProperties(name: string) {
        return {};
    }

    private async refreshNodeCatalogue() {
        const nodesRes = await this.get('nodes');
        this.nodes = nodesRes;
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
        if (this.websocket) {
            this.websocket.addEventListener(eventType, callback);
        }
    }

    public removeWsEventListener(eventType: string, callback: EventListenerOrEventListenerObject) {
        this.listeners.delete([eventType, callback]);
        if (this.websocket) {
            this.websocket.removeEventListener(eventType, callback);
        }
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
        return;
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
     * Image/Media API
     */
    public getImagePath(imageName: string) {
        return `http://${this.mediaHost}/${imageName}`;
    }

    private async mediaServerPut(path, data) {
        try {
            const response = await fetch(`http://${this.mediaHost}/${path}`, {
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

    public async setMediaServerVar(name: string, value: string): Promise<any> {
        return this.mediaServerPut('set', { [name]: value });
    }

    public async getMediaServerVars(): Promise<any> {
        return this.mediaServerPut('set', { });
    }
}

export const API = new ServerAPI();
