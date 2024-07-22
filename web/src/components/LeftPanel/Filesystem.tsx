import { Flex, Input, Tree, Button, Typography, Menu } from "antd";
import React, { useState, useMemo, useCallback, useEffect } from "react";
import { FileAddOutlined, FolderAddOutlined, UndoOutlined } from "@ant-design/icons";
import { useAPI } from "../../hooks/API";
import { keyRecursively } from "../../utils";
import { filesystemDragBegin } from "../../utils";
import DefaultWorkflow from "../../DefaultWorkflow.json";
import type { TreeProps, TreeDataNode } from 'antd';
const { Text } = Typography;
const { Search } = Input;

import './filesystem.css';

const getParentKey = (key: string, tree: any[]): string => {
    let parentKey;
    for (let i = 0; i < tree.length; i++) {
        const node = tree[i];
        if (node.children) {
            if (node.children.some((item) => item.key === key)) {
                parentKey = node.key;
            } else if (getParentKey(key, node.children)) {
                parentKey = getParentKey(key, node.children);
            }
        }
    }
    return parentKey;
};

export default function Filesystem({ setWorkflow, onBeginEdit }) {
    const [files, setFiles] = useState<any[]>([]);
    const [filesRoot, setFilesRoot] = useState('.');
    const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
    const [searchValue, setSearchValue] = useState('');
    const [autoExpandParent, setAutoExpandParent] = useState(true);
    const [addingState, setAddingState] = useState({ isAddingItem: false, isAddingFile: true });
    const [contextMenu, setContextMenu] = useState<{ x: number, y: number, filename: string } | null>(null);
    const [renamingState, setRenamingState] = useState({ isRenaming: false, filename: '' });
    const API = useAPI();

    useEffect(() => {
        const removeContextMenu = () => {
            setContextMenu(null);
        };

        window.addEventListener('click', removeContextMenu);
        return () => {
            window.removeEventListener('click', removeContextMenu);
        };
    }, []);

    const getFiles = useCallback(async () => {
        if (API === null) {
            return;
        }
        const files = await API.listFiles();
        if (!files) {
            return;
        }
        const splitPath = files.children[0].from_root.split('/');
        const filesRoot = splitPath[splitPath.length - 1];
        setFiles(files.children);
        setFilesRoot(filesRoot);
    }, [API]);

    useEffect(() => {
        getFiles();
    }, [API]);

    const onExpand = (newExpandedKeys) => {
        setExpandedKeys(newExpandedKeys);
        setAutoExpandParent(false);
    };

    const onSearchChange = (e) => {
        const { value } = e.target;
        const newExpandedKeys: string[] = [];
        const findExpandedKeys = (data) => {
            data.forEach((item) => {
                if (item.children) {
                    findExpandedKeys(item.children);
                }
                if (item.title.indexOf(value) > -1) {
                    newExpandedKeys.push(getParentKey(item.key, files));
                }
            });
        }
        findExpandedKeys(files);
        setExpandedKeys(newExpandedKeys);
        setSearchValue(value);
        setAutoExpandParent(true);
    };

    const onFileItemClick = useCallback((selectedKeys, { node }) => {
        if (!node) {
            onBeginEdit(null);
            return;
        }
        const { filename } = node.title.props;
        if (!filename) {
            onBeginEdit(null);
            return;
        }
        if (filename.slice(-3) == '.py') {
            onBeginEdit({ name: filename });
        } else if (filename.slice(-5) == '.json') {
            setWorkflow(filename);
            onBeginEdit(null);
        } else {
            onBeginEdit(null);
        }
    }, []);

    const onFileItemRightClick = useCallback(({ event, node }) => {
        setContextMenu({ x: event.clientX, y: event.clientY, filename: node.title.props.filename });
    }, []);

    const onItemRename = useCallback(async (newFilename) => {
        if (API) {
            await API.mvFile(renamingState.filename, newFilename);
            getFiles();
        }
        setRenamingState({ isRenaming: false, filename: '' });
    }, [API, renamingState]);

    const onItemDelete = useCallback(async (filename) => {
        if (API) {
            await API.rmFile(filename);
            getFiles();
        }
    }, [API]);

    const onAddItem = useCallback(async (e, isFile) => {
        const { value } = e.target;
        if (!value) {
            setAddingState({ isAddingItem: false, isAddingFile: true });
            return;
        }
        try {
            if (API) {
                const filename = e.target.value;
                const content = filename.endsWith('.json') ? DefaultWorkflow : "";
                await API.putFile(filename, isFile, JSON.stringify(content));
                setWorkflow(filename);
                getFiles();
            }
        } catch (e) {
            console.error(e);
        }
        setAddingState({ isAddingItem: false, isAddingFile: true });
    }, [API]);

    const treeData = useMemo(() => {
        const loop = (data, parentName = "") => (
            data.map((item) => {
                const strTitle = item.title;
                const filename = parentName + strTitle;
                const index = strTitle.indexOf(searchValue);
                const beforeStr = strTitle.substring(0, index);
                const afterStr = strTitle.slice(index + searchValue.length);
                let title =
                    index > -1 ? (
                        <span>
                            {beforeStr}
                            <span style={{ color: 'orange' }}>{searchValue}</span>
                            {afterStr}
                        </span>

                    ) : (
                        <span>
                            {strTitle}
                        </span>
                    );

                if (item.children) {
                    title = (
                        <DirItem
                            title={title}
                            filename={filename}
                            isRenaming={renamingState.isRenaming && filename === renamingState.filename}
                            onRename={onItemRename}
                        />
                    );
                    return { ...item, title, children: loop(item.children, filename + "/"), isLeaf: false, strTitle };
                }

                title = (
                    <FileItem
                        title={title}
                        filename={filename}
                        fullpath={item.path}
                        isRenaming={renamingState.isRenaming && filename === renamingState.filename}
                        onRename={onItemRename}
                    />
                );


                return {
                    ...item,
                    title,
                    isLeaf: true,
                    strTitle
                };
            }).sort((a, b) => {
                if (a.isLeaf !== b.isLeaf) {
                    return a.isLeaf ? 1 : -1;
                }

                return a.strTitle.localeCompare(b.strTitle);
            })
        );

        const currItems = loop(files);
        const { isAddingItem, isAddingFile } = addingState;
        const callback = (e) => onAddItem(e, isAddingFile);
        const pendingItem = {
            title: <span><Input className="add-fs-item-input" autoFocus={true} onBlur={callback} onPressEnter={callback} /></span>,
            isLeaf: isAddingFile,
            selectable: false,
            disabled: true
        };
        const items = isAddingItem ? [...currItems, pendingItem] : currItems;
        return keyRecursively(items);
    }, [searchValue, files, addingState, renamingState]);

    const contextMenuItems = useMemo(() => {
        return [
            {
                key: 'rename',
                label: 'Rename',
            },
            {
                key: 'delete',
                label: 'Delete',
            }
        ];
    }, []);

    const onContextMenuClick = useCallback(({ key }) => {
        if (contextMenu) {
            if (key === 'rename') {
                setRenamingState({ isRenaming: true, filename: contextMenu.filename });
            } else if (key === 'delete') {
                onItemDelete(contextMenu.filename);
            }
        }

        setContextMenu(null);
    }, [contextMenu]);

    const onDrop: TreeProps['onDrop'] = useCallback((info) => {
        console.log(info);
        const dropKey = info.node.key;
        const dragKey = info.dragNode.key;
        const dropPos = info.node.pos.split('-');
        const dropPosition = info.dropPosition - Number(dropPos[dropPos.length - 1]); // the drop position relative to the drop node, inside 0, top -1, bottom 1

        const loop = (
            data: TreeDataNode[],
            key: React.Key,
            callback: (node: TreeDataNode, i: number, data: TreeDataNode[]) => void,
        ) => {
            for (let i = 0; i < data.length; i++) {
                if (data[i].key === key) {
                    return callback(data[i], i, data);
                }
                if (data[i].children) {
                    loop(data[i].children!, key, callback);
                }
            }
        };
        const data = [...files];

        // Find dragObject
        let dragObj: TreeDataNode;
        loop(data, dragKey, (item, index, arr) => {
            arr.splice(index, 1);
            dragObj = item;
        });

        if (!info.dropToGap) {
            // Drop on the content
            loop(data, dropKey, (item) => {
                item.children = item.children || [];
                // where to insert. New item was inserted to the start of the array in this example, but can be anywhere
                item.children.unshift(dragObj);
            });
        } else {
            let ar: TreeDataNode[] = [];
            let i: number;
            loop(data, dropKey, (_item, index, arr) => {
                ar = arr;
                i = index;
            });
            if (dropPosition === -1) {
                // Drop on the top of the drop node
                ar.splice(i!, 0, dragObj!);
            } else {
                // Drop on the bottom of the drop node
                ar.splice(i! + 1, 0, dragObj!);
            }
        }
        setFiles(files);
    }, [files]);

    return (
        <div className="filesystem">
            <Search style={{ marginBottom: 8 }} placeholder="Search" onChange={onSearchChange} />
            <Flex justify="space-between">
                <Text>{filesRoot}/</Text>
                <div style={{ display: 'flex', flexDirection: 'row' }}>
                    <Button className="fs-icon" icon={<FileAddOutlined />} onClick={() => setAddingState({ isAddingItem: true, isAddingFile: true })} />
                    <Button className="fs-icon" icon={<FolderAddOutlined style={{ fontSize: '17px' }} />} onClick={() => setAddingState({ isAddingItem: true, isAddingFile: false })} />
                    <Button className="fs-icon" icon={<UndoOutlined style={{ fontSize: '15px' }} />} onClick={getFiles} />
                </div>
            </Flex>
            <Tree.DirectoryTree
                onExpand={onExpand}
                expandedKeys={expandedKeys}
                autoExpandParent={autoExpandParent}
                treeData={treeData}
                onSelect={onFileItemClick}
                onRightClick={onFileItemRightClick}
                blockNode
                draggable
            />
            {contextMenu && (
                <Menu
                    style={{ position: 'fixed', top: contextMenu.y, left: contextMenu.x, zIndex: 100 }}
                    onClick={onContextMenuClick}
                    items={contextMenuItems}
                />
            )}
        </div>
    );

}

function DirItem({ title, filename, isRenaming, onRename }) {
    const [currentFilename, setCurrentFilename] = useState(filename);

    const onChange = useCallback((e) => {
        setCurrentFilename(e.target.value);
    }, []);

    const onDone = useCallback(() => {
        onRename(currentFilename);
    }, [currentFilename, onRename]);

    if (isRenaming) {
        return (
            <span className="file-item">
                <Input autoFocus={true} value={currentFilename} onChange={onChange} onBlur={onDone} onPressEnter={onDone} />
            </span>
        );
    }

    return (
        <span className="dir-item">
            {title}
        </span>
    );
}

function FileItem({ title, filename, fullpath, isRenaming, onRename }) {
    const [currentFilename, setCurrentFilename] = useState(filename);

    const onDragStart = useCallback((e) => {
        filesystemDragBegin(filename, e);
    }, [filename]);

    const onChange = useCallback((e) => {
        setCurrentFilename(e.target.value);
    }, []);

    const onDone = useCallback(() => {
        onRename(currentFilename);
    }, [currentFilename, onRename]);

    if (isRenaming) {
        return (
            <span className="file-item">
                <Input autoFocus={true} value={currentFilename} onChange={onChange} onBlur={onDone} onPressEnter={onDone} />
            </span>
        );
    }

    return (
        <span className="file-item" onDragStart={onDragStart} draggable>
            {title}
        </span>
    );
}