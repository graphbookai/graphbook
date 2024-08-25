import React from 'react';

export function ActiveOverlay({ isActive, backgroundColor, children }) {
    if (isActive) {
        return children;
    }
    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            {children}
            <div style={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                width: '100%', 
                height: '100%', 
                background: backgroundColor,
                opacity: 0.5,
                zIndex: 1000
            }} />
        </div>
    );
}
