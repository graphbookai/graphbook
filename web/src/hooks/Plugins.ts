import { useEffect, useState } from 'react';
import { useAPI } from './API';
import { Plugins } from '../plugins';
import type { PanelPlugin, NodePlugin, WidgetPlugin } from '../plugins';

let isInitialized = false;
let globalPanels: PanelPlugin[] = [];
let globalSteps: NodePlugin[] = [];
let globalResources: NodePlugin[] = [];
let globalWidgets: WidgetPlugin[] = [];
let localSetters: Function[] = [];
export function usePlugins() {
    const API = useAPI();
    const [_, setPlugins] = useState({
        panels: globalPanels,
        steps: globalSteps,
        resources: globalResources,
        widgets: globalWidgets
    });

    useEffect(() => {
        localSetters.push(setPlugins);

        const loadPlugins = async () => {
            if (!isInitialized && API) {
                isInitialized = true;
                await Plugins.loadPlugins(API);
                const panels = Plugins.getPanels();
                const steps = Plugins.getSteps();
                const resources = Plugins.getResources();
                const widgets = Plugins.getWidgets();
                globalPanels = panels;
                globalSteps = steps;
                globalResources = resources;
                globalWidgets = widgets;

                for (const setter of localSetters) {
                    setter({ panels, steps, resources, widgets });
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

    return {
        panels: globalPanels,
        steps: globalSteps,
        resources: globalResources,
        widgets: globalWidgets
    };
}


export function usePluginPanels() {
    const { panels } = usePlugins();
    return panels;
}

export function usePluginWidgets() {
    const { widgets } = usePlugins();
    return widgets;
}

export function usePluginSteps() {
    const { steps } = usePlugins();
    return steps;
}

export function usePluginResources() {
    const { resources } = usePlugins();
    return resources;
}
