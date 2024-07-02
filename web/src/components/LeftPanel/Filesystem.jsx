import { Flex, Input, Tree, Button, Typography } from "antd";
import { useState, useMemo, useCallback, useEffect } from "react";
import { FileAddOutlined, FolderAddOutlined, UndoOutlined } from "@ant-design/icons";
import { useAPI } from "../../hooks/API";
import { keyRecursively } from "../../utils";
import { filesystemDragBegin } from "../../utils";
const { Text } = Typography;
const { Search } = Input;

import './filesystem.css';

const initialFiles = [];

const getParentKey = (key, tree) => {
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
    const [files, setFiles] = useState(initialFiles);
    const [filesRoot, setFilesRoot] = useState('.');
    const [expandedKeys, setExpandedKeys] = useState([]);
    const [searchValue, setSearchValue] = useState('');
    const [autoExpandParent, setAutoExpandParent] = useState(true);
    const [addingState, setAddingState] = useState({ isAddingItem: false, isAddingFile: true });
    const API = useAPI();

    const getFiles = useCallback(async () => {
        if (API === null) {
            return;
        }
        const files = await API.listFiles();
        if (!files) {
            return;
        }
        const splitPath = files.children[0].from_root.split('/');
        const filesRoot = splitPath[splitPath.length-1];
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
        const newExpandedKeys = [];
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
            onBeginEdit({name: filename});
        } else if(filename.slice(-5) == '.json') {
            setWorkflow(filename);
            onBeginEdit(null);
        } else {
            onBeginEdit(null);
        }
    });

    const onAddItem = useCallback(async (e, isFile) => {
        const { value } = e.target;
        if (!value) {
            setAddingState({ isAddingItem: false, isAddingFile: true });
            return;
        }
        try {
            await API.putFile(e.target.value, isFile);
            getFiles();
        } catch (e) {
            console.error(e);
        }
        setAddingState({ isAddingItem: false, isAddingFile: true });
    });

    const treeData = useMemo(() => {
        const loop = (data, parentName="") => (
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
                            <span style={{color: 'orange'}}>{searchValue}</span>
                            {afterStr}
                        </span>
                
                    ) : (
                        <span>
                            {strTitle}
                        </span>
                    );

                if (item.children) {
                    title = <DirItem title={title}/>;
                    return { ...item, title, children: loop(item.children, filename + "/"), isLeaf: false, strTitle };
                }

                title = <FileItem title={title} filename={filename} fullpath={item.path} onClick={()=>onFileItemClick(title, filename)}/>;

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
            title: <span><Input className="add-fs-item-input" autoFocus={true} onBlur={callback} onPressEnter={callback}/></span>,
            isLeaf: isAddingFile,
            selectable: false,
            disabled: true
        };
        const items = isAddingItem ? [...currItems, pendingItem] : currItems;
        return keyRecursively(items);
    }, [searchValue, files, addingState]);

    return (
        <div className="filesystem">
            <Search style={{ marginBottom: 8 }} placeholder="Search" onChange={onSearchChange} />
            <Flex justify="space-between">
                <Text>{filesRoot}/</Text>
                <div style={{display: 'flex', flexDirection: 'row'}}>
                    <Button className="fs-icon" icon={<FileAddOutlined />} onClick={()=>setAddingState({ isAddingItem: true, isAddingFile: true })}/>
                    <Button className="fs-icon" icon={<FolderAddOutlined style={{fontSize: '17px'}}/>} onClick={()=>setAddingState({ isAddingItem: true, isAddingFile: false })}/>
                    <Button className="fs-icon" icon={<UndoOutlined style={{fontSize: '15px'}}/>} onClick={getFiles}/>
                </div>
            </Flex>
            <Tree.DirectoryTree
                onExpand={onExpand}
                expandedKeys={expandedKeys}
                autoExpandParent={autoExpandParent}
                treeData={treeData}
                blockNode
                onSelect={onFileItemClick}
            />
        </div>
    );

}

function DirItem({ title }) {
    return (
        <span className="dir-item">
            {title}
        </span>
    );
}

function FileItem({ title, filename, fullpath, onClick }) {
    const onDragStart = useCallback((e) => {
        filesystemDragBegin(filename, e);
    }, [filename]);

    return (
        <span className="file-item" onDragStart={onDragStart} draggable onClick={onClick}>
            {title}
        </span>
    );
}