module.exports = {
    entry: './src/main.tsx',
    output: {
        filename: 'bundle.js',        
        library: {
            type: 'module'
        },
    },
    experiments: {
        outputModule: true
    },
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/
            }
        ]
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js']
    },
    externalsType: 'window',
    externals: {
        react: 'react',
    }
};
