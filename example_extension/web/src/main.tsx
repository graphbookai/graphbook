console.log("Imported Plugin");
import React from "react";
import { ExamplePanel } from "./ExamplePanel";
import { ExampleNode } from "./ExampleNode";

export function ExportNodes() {
    return [{
        type: "Step",
        label: "Example Node",
        children: <ExampleNode />,
    }];
}

export function ExportPanels() {
    return [{
        label: "Example Panel",
        children: <ExamplePanel />,
    }];
}
