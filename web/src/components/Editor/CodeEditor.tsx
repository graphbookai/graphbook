import React, { useState, useCallback, useEffect, useRef } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { basicDark } from '@uiw/codemirror-theme-basic';
import { bbedit } from '@uiw/codemirror-theme-bbedit';
import { CloseOutlined, CheckOutlined, LoadingOutlined, UndoOutlined } from "@ant-design/icons";
import { theme, notification } from 'antd';
import { useAPI } from '../../hooks/API';
import { md5 } from 'js-md5';
import { Resizable } from 're-resizable';
const { useToken } = theme;

const UPDATE_EVERY = 1 * 1000;
const defaultEditorState = {
    isLoading: true,
    prevHash: "",
    value: "",
    isSaved: true
};

const generateMD5 = (content) => {
    const hash = md5.create();
    hash.update(content);
    return hash.hex();
};

export function CodeEditor({ closeEditor, name }) {
    const [notify, notificationContext] = notification.useNotification();
    const [codeEditorState, setCodeEditorState] = useState(defaultEditorState);
    const [gettingFile, setGettingFile] = useState(false);
    const currTimeout = useRef<number | null>(null);
    const API = useAPI();
    const { theme, token } = useToken();

    let filepath = name;
    if (filepath[0] === '/') {
        filepath = filepath.slice(1);
    }

    const getFile = useCallback(async () => {
        if (API && filepath) {
            try {
                setGettingFile(true);
                const file = await API.getFile(filepath);
                setCodeEditorState({
                    isLoading: false,
                    prevHash: generateMD5(file.content),
                    value: file.content,
                    isSaved: true
                });
            } catch {
                setCodeEditorState({
                    isLoading: false,
                    prevHash: "",
                    value: "",
                    isSaved: true
                });
                console.log("Error getting file");
            }
            setGettingFile(false);
        }
    }, [API, filepath])

    useEffect(() => {
        getFile();
    }, [API, filepath]);

    const onChange = useCallback((val, viewUpdate) => {
        if (!API) {
            return;
        }

        setCodeEditorState({
            ...codeEditorState,
            isSaved: false,
            value: val
        });
        if (currTimeout.current) {
            clearTimeout(currTimeout.current);
        }

        const timeout = setTimeout(async () => {
            console.log("Saving file...", filepath);
            const response = await API.putFile(filepath, true, val, codeEditorState.prevHash);
            if (!response.ok) {
                if (response.status === 409) {
                    notify.error({
                        message: "Error Saving",
                        description: "Conflicts found during saving. Refresh the file to show original contents.",
                        duration: 0,
                    })
                }
            } else {
                const newHash = generateMD5(val);
                setCodeEditorState({
                    ...codeEditorState,
                    isSaved: true,
                    prevHash: newHash,
                    value: val
                });
            }
        }, UPDATE_EVERY);
        currTimeout.current = timeout;
    }, [currTimeout, filepath, codeEditorState, API]);

    return (
        <Resizable
            defaultSize={{ width: 500 }}
            enable={{ right: true }}
            style={{ ...styles.container, backgroundColor: token.colorBgBase }}
            handleStyles={{ right: { backgroundColor: token.colorBorder, width: 5 } }}
        >
            {notificationContext}
            <div style={styles.header}>
                <div style={styles.title}>
                    <div style={{ margin: '0 5px' }}>{name}</div>
                    <div style={{ margin: '0 5px' }}>
                        {codeEditorState.isSaved ?
                            <div><CheckOutlined style={{ color: 'green' }} /> Saved</div>
                            :
                            <div><LoadingOutlined /> Pending changes</div>
                        }
                    </div>
                    <UndoOutlined title="Refresh" style={{ margin: '0 5px' }} spin={gettingFile} onClick={getFile} />
                </div>
                <CloseOutlined onClick={closeEditor} />
            </div>
            <CodeMirror
                style={{ overflow: 'auto' }}
                theme={theme.id == 0 ? bbedit : basicDark}
                value={codeEditorState.value}
                editable={!codeEditorState.isLoading}
                extensions={[python()]}
                onChange={onChange}
            />
        </Resizable>
    );
}

type StyleSheet = {
    [key: string]: React.CSSProperties
};
const styles: StyleSheet = {
    container: {
        position: 'absolute',
        zIndex: 5,
        top: 0,
        bottom: 0,
        display: 'flex',
        flexDirection: 'column'
    },
    header: {
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'space-between',
        overflowX: 'hidden',
        minHeight: '30px'
    },
    title: {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        margin: '5px',
    }
};
