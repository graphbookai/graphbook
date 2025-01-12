import { Flex, Input, Tree, Button, Typography, Menu, theme } from "antd";
import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { FileAddOutlined, FolderAddOutlined, UndoOutlined } from "@ant-design/icons";
import { useAPI } from "../../hooks/API";
import { bindDragData } from "../../utils";
import { ActiveOverlay } from "../ActiveOverlay";
import DefaultWorkflow from "../../DefaultWorkflow.json";
import type { TreeProps } from 'antd';
const { Text } = Typography;
const { Search } = Input;

import './filesystem.css';
import Executions from "./Executions";


export default function Filesystem({ setWorkflow, onBeginEdit }) {
    const [isDisabled, setIsDisabled] = useState(false);
    const [files, setFiles] = useState<any[]>([]);
    const [filesRoot, setFilesRoot] = useState('.');
    const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
    const [searchValue, setSearchValue] = useState('');
    const [autoExpandParent, setAutoExpandParent] = useState(true);
    const [addingState, setAddingState] = useState({ isAddingItem: false, isAddingFile: true });
    const [contextMenu, setContextMenu] = useState<{ x: number, y: number, filename: string } | null>(null);
    const [renamingState, setRenamingState] = useState({ isRenaming: false, filename: '' });
    const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
    const { token } = theme.useToken();
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
            setIsDisabled(true);
            setFilesRoot('(Editor disabled)');
            return;
        }

        setIsDisabled(false);
        const filesRoot = files.title.toUpperCase();
        const setKey = (data) => {
            data.forEach((item) => {
                item.key = item.path;
                if (item.children) {
                    setKey(item.children);
                }
            });
        };
        setKey(files.children);
        setFiles(files.children);
        setFilesRoot(filesRoot);

        if (!selectedWorkflow) {
            const anyJson = files.children.find((item) => {
                const filename = item.path;
                return filename.slice(-5) === '.json';
            });
            if (anyJson) {
                setWorkflow(anyJson.path);
                setSelectedWorkflow(anyJson.path);
            }
        }
    }, [API, selectedWorkflow]);

    useEffect(() => {
        getFiles();
    }, [API]);

    const onExpand = (newExpandedKeys) => {
        setExpandedKeys(newExpandedKeys);
        setAutoExpandParent(false);
    };

    const onSearchChange = useCallback((e) => {
        const { value } = e.target;
        const newExpandedKeys: string[] = [];
        const findExpandedKeys = (data, parentKey: string | null) => {
            data.forEach((item) => {
                if (item.children) {
                    findExpandedKeys(item.children, item.key);
                }
                if (item.path.indexOf(value) > -1 && parentKey) {
                    newExpandedKeys.push(parentKey);
                }
            });
        };
        findExpandedKeys(files, null);
        setExpandedKeys(newExpandedKeys);
        setSearchValue(value);
        setAutoExpandParent(true);
    }, [files]);

    const onFileItemClick = useCallback((selectedKeys, { node }) => {
        if (!node) {
            onBeginEdit(null);
            return;
        }
        const filename = node.path;
        if (!filename) {
            onBeginEdit(null);
            return;
        }
        if (filename.slice(-3) == '.py') {
            console.log("Attempting to open", filename)
            onBeginEdit({ name: filename });
        } else if (filename.slice(-5) == '.json') {
            setWorkflow(filename);
            setSelectedWorkflow(filename);
            onBeginEdit(null);
        } else {
            onBeginEdit(null);
        }
    }, []);

    const onExecutionClick = useCallback((executionName: string) => {
        console.log("Execution clicked", executionName);
    }, []);

    const onFileItemRightClick = useCallback(({ event, node }) => {
        setContextMenu({ x: event.clientX, y: event.clientY, filename: node.path });
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
            if (filename === selectedWorkflow) {
                setWorkflow(null);
                setSelectedWorkflow(null);
            }
        }
    }, [API, selectedWorkflow]);

    const onAddItem = useCallback(async (e, isFile) => {
        const { value } = e.target;
        if (!value) {
            setAddingState({ isAddingItem: false, isAddingFile: true });
            return;
        }
        try {
            if (API) {
                const filename = e.target.value;
                const isJSON = filename.endsWith('.json');
                const content = isJSON ? DefaultWorkflow : "";
                await API.putFile(filename, isFile, JSON.stringify(content));
                if (isJSON) {
                    setWorkflow(filename);
                    setSelectedWorkflow(filename);
                }
                getFiles();
            }
        } catch (e) {
            console.error(e);
        }
        setAddingState({ isAddingItem: false, isAddingFile: true });
    }, [API]);

    const treeData = useMemo(() => {
        const loop = (data) => (
            data.map((item) => {
                const strTitle = item.title;
                const filename = item.path;
                const index = strTitle.indexOf(searchValue);
                const beforeStr = strTitle.substring(0, index);
                const afterStr = strTitle.slice(index + searchValue.length);
                let title =
                    index > -1 ? (
                        <Text ellipsis>
                            {beforeStr}
                            <span style={{ color: 'orange' }}>{searchValue}</span>
                            {afterStr}
                        </Text>

                    ) : (
                        <Text ellipsis>
                            {strTitle}
                        </Text>
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
                    return { ...item, title, children: loop(item.children), isLeaf: false, strTitle };
                }

                title = (
                    <FileItem
                        title={title}
                        filename={filename}
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
        return items;
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

    const onDragStart: TreeProps['onDragStart'] = useCallback(({ event, node }) => {
        if (node.path.endsWith('.json')) {
            bindDragData({ subflow: node.path }, event);
        } else {
            bindDragData({ text: node.path_from_cwd }, event);
        }
    }, []);

    const onDrop: TreeProps['onDrop'] = useCallback(async (info) => {
        if (!API) {
            return;
        }
        const basename = (p) => {
            const parts = p.split('/');
            return parts[parts.length - 1];
        };
        const itemDragged = info.dragNode.path;
        const itemDraggedBasename = basename(itemDragged);
        const newDir = !info.dropToGap ? info.node.dirname + "/" + basename(info.node.path) : info.node.dirname;
        let newItemDraggedName = newDir + "/" + itemDraggedBasename;
        if (newItemDraggedName[0] === '/') {
            newItemDraggedName = newItemDraggedName.slice(1);
        }

        await API.mvFile(itemDragged, newItemDraggedName);
        getFiles();
    }, [API]);

    return (
        <ActiveOverlay backgroundColor={token.colorBgBase} isActive={API !== null}>
            <Flex vertical className="filesystem">
                <Search style={{ marginBottom: 5 }} placeholder="Search" onChange={onSearchChange} />
                <Flex justify="space-between" align="center">
                    <Text ellipsis style={{ fontWeight: 'bold' }}>{filesRoot}</Text>
                    <Flex>
                        <Button disabled={isDisabled} className="fs-icon" icon={<FileAddOutlined />} onClick={() => setAddingState({ isAddingItem: true, isAddingFile: true })} />
                        <Button disabled={isDisabled} className="fs-icon" icon={<FolderAddOutlined style={{ fontSize: '17px' }} />} onClick={() => setAddingState({ isAddingItem: true, isAddingFile: false })} />
                        <Button disabled={isDisabled} className="fs-icon" icon={<UndoOutlined style={{ fontSize: '15px' }} />} onClick={getFiles} />
                    </Flex>
                </Flex>
                <Flex vertical style={{ height: '100%' }}>
                    <div style={{ overflowY: 'auto', overflowX: 'hidden' }}>
                        <Tree.DirectoryTree
                            onExpand={onExpand}
                            expandedKeys={expandedKeys}
                            autoExpandParent={autoExpandParent}
                            selectedKeys={selectedWorkflow ? [selectedWorkflow] : []}
                            treeData={treeData}
                            onSelect={onFileItemClick}
                            onRightClick={onFileItemRightClick}
                            onDrop={onDrop}
                            onDragStart={onDragStart}
                            blockNode
                            draggable
                        />
                    </div>
                    <Executions setWorkflow={setWorkflow} />
                </Flex>
            </Flex>
            {contextMenu && (
                <Menu
                    style={{ position: 'fixed', top: contextMenu.y, left: contextMenu.x, zIndex: 100 }}
                    onClick={onContextMenuClick}
                    items={contextMenuItems}
                />
            )}
        </ActiveOverlay>
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

function FileItem({ title, filename, isRenaming, onRename }) {
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
        <span className="file-item">
            {title}
        </span>
    );
}
