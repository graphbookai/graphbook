import React, { useCallback, useState } from 'react';
import { Flex } from 'antd';
import { NodeResizer } from 'reactflow';
import { Node } from 'reactflow';

export function Group({ id, data, selected, width, height }) {
    const { name } = data;
    const [size, setSize] = useState({ width, height });
    const style = {
        width: size.width,
        height: size.height,
        backgroundColor: '#f0f0f080',
    };

    const onResize = useCallback((e, { width, height }) => {
        setSize({ width, height });
    }, []);

    return (
        <div>
            <NodeResizer minWidth={200} minHeight={200} onResize={onResize} />
            <div className="group-node" style={style}>
                <Flex gap="small" justify='space-between'>
                    <span>Group</span>
                    <div>{name}</div>
                </Flex>
            </div>
        </div>
    );
}


export function groupIfPossible(changedNodes: Node[], allNodes: Node[]) {
    const groupNodes = allNodes.filter((node) => node.type === 'group');
    const changedNodesIds = changedNodes.map(({ id }) => id);
    return allNodes.map((node) => {
        if (node.type === 'group' || !changedNodesIds.includes(node.id)) {
            return node;
        }

        const { position, width, height } = node;
        if (!width || !height) {
            return node;
        }

        for(const groupNode of groupNodes) {
            const gpos = groupNode.position;
            const w = groupNode.width;
            const h = groupNode.height;
            if (!w || !h) {
                continue;
            }
            const groupBounds = [gpos.x, gpos.y, gpos.x + w, gpos.y + h];

            if(node.parentId === groupNode.id) {
                if (!(position.x > 0 &&
                    position.y > 0 &&
                    position.x + width < w &&
                    position.y + height < h)
                ) {
                    node.parentId = '';
                    node.position = { x: position.x + gpos.x, y: position.y + gpos.y };
                }
            } else {
                if (position.x > groupBounds[0] &&
                    position.y > groupBounds[1] &&
                    position.x + width < groupBounds[2] &&
                    position.y + height < groupBounds[3]
                ) {
                    node.parentId = groupNode.id;
                    node.position = { x: position.x - gpos.x, y: position.y - gpos.y };
                }
            }
        }

        return node;
    });
}
