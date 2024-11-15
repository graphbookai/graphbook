import React from "react";
import { Tooltip } from "antd";
import { useSettings } from "../hooks/Settings";

export function RemovableTooltip({ title, children }: {title: string | undefined, children: any}) {
    const [settings] = useSettings();
    if (settings.disableTooltips) {
        return children;
    }

    return <Tooltip title={title}>{children}</Tooltip>;
}
