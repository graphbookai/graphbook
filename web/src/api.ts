import { Node, Edge } from 'reactflow';

const RECONNECT_INTERVAL = 2; // Number of seconds to wait before attempting to reconnect

export class ServerAPI {
    private host: string;
    private mediaHost: string;
    private nodes: any;
    private websocket: WebSocket | null;
    private listeners: Set<[string, EventListenerOrEventListenerObject]>
    private reconnectListeners: Set<Function>;

    constructor() {
        this.nodes = {};
        this.listeners = new Set();
        this.reconnectListeners = new Set();
    }

    public connect(host: string, mediaHost: string) {
        this.host = host;
        this.mediaHost = mediaHost;
        this.connectWebSocket();
    }

    public disconnect() {
        if (this.websocket) {
            this.websocket.onclose = null;
            this.websocket.close();
            this.websocket = null;
        }
    }

    private connectWebSocket() {
        const connect = () => {
            try {
                this.websocket = new WebSocket(`ws://${this.host}/ws`);
            } catch (e) {
                console.error(e);
                return;
            }
            for (const [eventType, callback] of this.listeners) {
                this.websocket.addEventListener(eventType, callback);
            }
            this.websocket.onopen = () => {
                console.log("Connected to server.");
                this.refreshNodeCatalogue();
            };
            this.websocket.onclose = () => {
                this.retryWebSocketConnection();
            };
        };
        if (this.websocket) {
            if (this.websocket.readyState === WebSocket.OPEN || this.websocket.readyState === WebSocket.CONNECTING) {
                console.log("Must disconnect websocket before reconnecting.");
            } else if (this.websocket.readyState === WebSocket.CLOSING) {
                this.websocket.onclose = () => connect();
            } else {
                connect();
            }
        } else {
            connect();
        }
    }

    private retryWebSocketConnection() {
        const reconnectSecond = (i) => {
            setTimeout(() => {
                if (this.isWebSocketOpen()) {
                    return;
                }

                if (i <= 0 && this.websocket) {
                    console.log("Retrying connection to server...");
                    this.connectWebSocket();
                } else {
                    reconnectSecond(i - 1);
                }
                for (const callback of this.reconnectListeners) {
                    callback(i);
                }
            }, 1000);
        };
        reconnectSecond(RECONNECT_INTERVAL);
    }

    private isWebSocketOpen(): boolean {
        return this.websocket != null && this.websocket.readyState === WebSocket.OPEN;
    }

    public getHost() {
        return this.host;
    }

    public getMediaHost() {
        return this.mediaHost;
    }

    public setHost(host: string) {
        this.host = host;
        this.disconnect();
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

    private async post(path, data): Promise<any> {
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

    private async put(path, data): Promise<Response> {
        const response = await fetch(`http://${this.host}/${path}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        return response;
    }

    private async get(path): Promise<any> {
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

    private async delete(path): Promise<any> {
        try {
            const response = await fetch(`http://${this.host}/${path}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
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

    public addReconnectListener(callback: Function) {
        this.reconnectListeners.add(callback);
    }

    public removeReconnectListener(callback: Function) {
        this.reconnectListeners.delete(callback);
    }

    /**
     * Processor API
     */
    public async runAll(graph, resources, filename) {
        return await this.post('run', { graph, resources, filename });
    }

    public async run(graph, resources, stepId, filename) {
        return await this.post(`run/${stepId}`, { graph, resources, filename });
    }

    public async step(graph, resources, stepId, filename) {
        return await this.post(`step/${stepId}`, { graph, resources, filename });
    }

    public async pause() {
        return await this.post('pause', {});
    }

    public async clearAll() {
        return await this.post('clear', {});
    }

    public async clear(nodeId) {
        return await this.post(`clear/${nodeId}`, {});
    }

    public async getNodes() {
        return await this.get('nodes');
    }

    public async getState(stepId: string, pin: string, index: number) {
        return await this.get(`state/${stepId}/${pin}/${index}`);
    }

    public async getRunState() {
        return await this.get('state');
    }

    public async respondToPrompt(stepId: string, response: any) {
        return await this.post(`prompt_response/${stepId}`, { response });
    }

    /**
     * File API
     */
    public async listFiles() {
        const workflowFiles = await this.get('fs?stat=true');
        return workflowFiles;
    }

    public async putFile(filepath: string, isFile: boolean, content: string = '', hash_key: string = '') {
        return await this.put(`fs/${filepath}`, {
            is_file: isFile,
            file_contents: content,
            hash_key: hash_key
        });
    }

    public async mvFile(oldPath, newPath) {
        return await this.put(`fs/${oldPath}?mv=${newPath}`, {});
    }

    public async getFile(filepath) {
        return await this.get(`fs/${filepath}`);
    }

    public async rmFile(filepath) {
        return await this.delete(`fs/${filepath}`);
    }

    public async getSubflowFromFile(filepath) {
        const res = await this.getFile(filepath);
        if (res?.content) {
            const jsonData = JSON.parse(res.content);
            if (jsonData?.type === 'workflow') {
                return { nodes: jsonData.nodes, edges: jsonData.edges };
            }
        }
        return null;
    }

    public async getWorkflowDoc(workflowFilename: string) {
        const filename = workflowFilename.replace('.json', '.md');
        return await this.get(`docs/${filename}`);
    }

    public async getStepDocstring(name: string) {
        return await this.get(`step_docstring/${name}`);
    }

    public async getResourceDocstring(name: string) {
        return await this.get(`resource_docstring/${name}`);
    }

    /**
     * Graph API
     */
    public putGraph(filename: string, nodes: Node[], edges: Edge[]) {
        if (!this.isWebSocketOpen()) {
            return;
        }
        this.websocket?.send(JSON.stringify({
            api: "graph",
            cmd: "put_graph",
            filename: filename,
            nodes: nodes,
            edges: edges
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

    /**
     * Plugins
     */
    public async getPluginList() {
        return await this.get('plugins');
    }
}

export const API = new ServerAPI();
