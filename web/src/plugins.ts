import type { ServerAPI } from './api';
import { useAPI, useAPIMessage } from './hooks/API';
import React from 'react';
import ReactDOM from 'react-dom'

window['react'] = React;
window['react-dom'] = ReactDOM;

class PluginManager {
    private plugins: Map<string, any>;

    constructor() {
        this.plugins = new Map();
    }

    public async loadPlugins(API: ServerAPI) {
        const plugins = await API.getPluginList();
        console.log("plugin list", plugins);
        if (!plugins) {
            return;
        }

        for await (const p of plugins) {
            if (!this.plugins.has(p)) {
                try {
                    const url = `http://${API.getHost()}/plugins/${p}`;
                    console.log("Loading plugin from", url);
                    const module = await import(url);
                    console.log(module.ReactFromModule);
                    this.plugins.set(p, module);
                    console.log(`Plugin ${p} loaded successfully`);
                } catch (error) {
                    console.error(`Failed to load plugin ${p}: ${error.message}`);
                }
            }
        }
    }

    public async reloadPlugins(API: ServerAPI) {
        this.plugins.clear();
        await this.loadPlugins(API);
    }

    public getPanels(): PanelPlugin[] {
        const panels: PanelPlugin[] = [];
        for (const p of this.plugins.values()) {
            if (p.ExportPanels) {
                panels.push(...p.ExportPanels(GraphbookAPI));
            }
        }
        console.log(panels);
        return panels;
    }

    public getNodes(): NodePlugin[] {
        const nodes: NodePlugin[] = [];
        for (const p of this.plugins.values()) {
            if (p.ExportNodes) {
                nodes.push(...p.ExportNodes());
            }
        }
        return nodes;
    }
}

export const Plugins = new PluginManager();

export type PanelPlugin = {
    label: string,
    icon?: JSX.Element,
    children: JSX.Element,
};

export type NodePlugin = {
    type: string,
    label: string,
    children: JSX.Element,
};

export const GraphbookAPI = {
    useAPI,
    useAPIMessage
};
