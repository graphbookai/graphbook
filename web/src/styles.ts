import type { GlobalToken } from "antd";

export const recordCountBadgeStyle = (token: GlobalToken) => {
    return {
        fontSize: 8,
        height: 10,
        lineHeight: '10px',
        padding: '0px 1px',
        borderRadius: '2px',
        marginRight: 2,
        backgroundColor: token.colorBgBase,
        border: `1px solid ${token.colorPrimaryBorder}`,
        color: token.colorPrimaryText,
    };
}

export const nodeBorderStyle = (token: GlobalToken, errored: boolean, selected: boolean, parentSelected: boolean) => {
    const baseStyle = {
        padding: '1px',
        borderRadius: token.borderRadius,
        transform: 'translate(-2px, -2px)'
    };

    const selectedStyle = {
        ...baseStyle,
        border: `1px dashed ${token.colorInfoActive}`
    };

    const erroredStyle = {
        ...baseStyle,
        border: `1px solid ${token.colorError}`,
    };

    const parentSelectedStyle = {
        ...baseStyle,
        border: `1px dashed ${token.colorInfoBorder}`
    };

    if (errored) {
        return erroredStyle;
    }

    if (selected) {
        return selectedStyle;
    }

    if (parentSelected) {
        return parentSelectedStyle;
    }

    return {};
};

const handleStyle = {
    borderRadius: '50%',
    left: 0,
    right: 0,
};

export const inputHandleStyle = () => {
    return {
        ...handleStyle,
        marginRight: '2px'
    };
};

export const outputHandleStyle = () => {
    return {
        ...handleStyle,
        marginLeft: '2px',
    };
};
