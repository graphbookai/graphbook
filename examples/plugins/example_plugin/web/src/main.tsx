console.log("Imported Plugin");
import React from "react";
import { ExamplePanel } from "./ExamplePanel";
import { ExampleNode } from "./ExampleNode";
export { default as ReactFromModule } from 'react'

type GraphbookAPI = {
    useAPI: Function,
    useAPIMessage: Function,
    useAPINodeMessage: Function,
};

export function ExportResources(graphbookAPI: GraphbookAPI) {
    return [{
        for: {
            name: "SimpleResource",
        },
        component: ExampleNode,
    }];
}

export function ExportPanels(graphbookAPI: GraphbookAPI) {
    console.log(graphbookAPI);
    const { useAPIMessage } = graphbookAPI;
    return [{
        label: "Example Panel",
        children: <ExamplePanel useAPIMessage={useAPIMessage}/>,
    }];
}
