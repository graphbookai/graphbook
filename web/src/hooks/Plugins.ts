import { useEffect, useState } from 'react';
import { useAPI } from './API';
import { Plugins } from '../plugins';
import type { PanelPlugin } from '../plugins';

let isInitialized = false;
let globalPanels: PanelPlugin[] = [];
let globalNodes: any[] = [];
let localSetters: Function[] = [];
export function usePlugins() {
    const API = useAPI();
    const [_, setPlugins] = useState({ panels: globalPanels, nodes: globalNodes });

    useEffect(() => {
        localSetters.push(setPlugins);

        const loadPlugins = async () => {
            if (!isInitialized && API) {
                isInitialized = true;
                await Plugins.loadPlugins(API);
                const panels = Plugins.getPanels();
                const nodes = Plugins.getNodes();
                globalPanels = panels;
                globalNodes = nodes;

                for (const setter of localSetters) {
                    setter({ panels, nodes });
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

    return { panels: globalPanels, nodes: globalNodes };
}


export function usePluginPanels() {
    const { panels } = usePlugins();
    return panels;
}

export function usePluginNodes() {
    const { nodes } = usePlugins();
    return nodes;
}
