import { useEffect, useState } from 'react';
import { useAPI } from './API';
import { Plugins } from '../plugins';
import type { PanelPlugin, NodePlugin, WidgetPlugin } from '../plugins';

let isInitialized = false;
let globalPanels: PanelPlugin[] = [];
let globalNodes: NodePlugin[] = [];
let globalWidgets: WidgetPlugin[] = [];
let localSetters: Function[] = [];
export function usePlugins() {
    const API = useAPI();
    const [_, setPlugins] = useState({ panels: globalPanels, nodes: globalNodes, widgets: globalWidgets });

    useEffect(() => {
        localSetters.push(setPlugins);

        const loadPlugins = async () => {
            if (!isInitialized && API) {
                isInitialized = true;
                await Plugins.loadPlugins(API);
                const panels = Plugins.getPanels();
                const nodes = Plugins.getNodes();
                const widgets = Plugins.getWidgets();
                globalPanels = panels;
                globalNodes = nodes;
                globalWidgets = widgets;

                for (const setter of localSetters) {
                    setter({ panels, nodes, widgets });
                }
            }
        };

        loadPlugins();

        return () => {
            localSetters = localSetters.filter((setter) => setter !== setPlugins);
            if (localSetters.length === 0) {
                isInitialized = false;
            }
        };
    }, [API]);

    return { panels: globalPanels, nodes: globalNodes, widgets: globalWidgets };
}


export function usePluginPanels() {
    const { panels } = usePlugins();
    return panels;
}

export function usePluginNodes() {
    const { nodes } = usePlugins();
    return nodes;
}

export function usePluginWidgets() {
    const { widgets } = usePlugins();
    return widgets;
}
