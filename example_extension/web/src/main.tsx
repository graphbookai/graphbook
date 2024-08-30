console.log("Imported Plugin");
import React from "react";
import { ExamplePanel } from "./ExamplePanel";
import { ExampleNode } from "./ExampleNode";
export { default as ReactFromModule } from 'react'

type GraphbookAPI = {
    useAPI: Function,
    useAPIMessage: Function,
};

export function ExportNodes(graphbookAPI: GraphbookAPI) {
    return [{
        type: "Step",
        label: "Example Node",
        children: <ExampleNode />,
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
