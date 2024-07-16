import type { GlobalToken } from "antd";

export const recordCountBadgeStyle = (token: GlobalToken) => {
    return {
        fontSize: 8,
        height: 10,
        lineHeight: '10px',
        padding: '0px 1px',
        borderRadius: '25%',
        marginRight: 2,
        backgroundColor: token.colorBgBase,
        border: `1px solid ${token.colorPrimaryBorder}`,
        color: token.colorPrimaryText,
    };
}
