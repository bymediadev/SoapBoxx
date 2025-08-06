# Transcription Service Switching Functionality

## Overview

The SoapBoxx application now supports switching between different transcription services on the SoapBoxx tab. Users can seamlessly switch between local Whisper, OpenAI Whisper API, AssemblyAI, and Azure Speech Services without restarting the application.

## Supported Services

### 1. Local Whisper
- **Description**: Local transcription using OpenAI's Whisper model
- **Requirements**: `openai-whisper` package installed
- **Model Size**: Base (configurable)
- **Pros**: No API costs, works offline, privacy-focused
- **Cons**: Requires more computational resources, slower than cloud services

### 2. OpenAI Whisper API
- **Description**: Cloud-based transcription using OpenAI's Whisper API
- **Requirements**: OpenAI API key configured
- **Pros**: High accuracy, fast processing, reliable
- **Cons**: Requires API key, costs per usage

### 3. AssemblyAI
- **Description**: Professional speech-to-text API
- **Requirements**: AssemblyAI API key configured
- **Pros**: High accuracy, speaker diarization, custom models
- **Cons**: Requires API key, costs per usage

### 4. Azure Speech Services
- **Description**: Microsoft's speech-to-text service
- **Requirements**: Azure Speech key configured
- **Pros**: Enterprise-grade, multiple languages, custom models
- **Cons**: Requires API key, costs per usage

## Implementation Details

### Backend Changes

#### `backend/soapboxx_core.py`
- Added `transcription_service` parameter to `__init__` method
- Added `set_transcription_service()` method for dynamic service switching
- Proper API key handling for different services

#### `backend/transcriber.py`
- Enhanced service initialization with proper API key handling
- Added `get_local_model_info()` method for local service status
- Improved error handling and service validation

### Frontend Changes

#### `frontend/soapboxx_tab.py`
- Added transcription service selection dropdown
- Real-time service status updates
- Dynamic service switching during recording sessions
- Proper error handling and user feedback

## Usage Instructions

### In the UI

1. **Open the SoapBoxx application**
2. **Navigate to the SoapBoxx tab**
3. **Select your preferred transcription service**:
   - Use the "Service" dropdown in the "🔧 Transcription Service" section
   - Available options: `openai`, `local`, `assemblyai`, `azure`
4. **Check service status**:
   - Green status indicates service is ready
   - Red status indicates configuration issues
5. **Start recording**:
   - The selected service will be used for transcription
   - You can switch services between recording sessions

### Service Configuration

#### Local Whisper
```bash
# Install Whisper
pip install openai-whisper

# The service will automatically download the base model on first use
```

#### OpenAI Whisper API
```bash
# Set environment variable
export OPENAI_API_KEY="your-api-key-here"

# Or add to .env file
echo "OPENAI_API_KEY=your-api-key-here" >> .env
```

#### AssemblyAI
```bash
# Set environment variable
export ASSEMBLYAI_API_KEY="your-api-key-here"

# Or add to .env file
echo "ASSEMBLYAI_API_KEY=your-api-key-here" >> .env
```

#### Azure Speech Services
```bash
# Set environment variables
export AZURE_SPEECH_KEY="your-speech-key-here"
export AZURE_SPEECH_REGION="eastus"

# Or add to .env file
echo "AZURE_SPEECH_KEY=your-speech-key-here" >> .env
echo "AZURE_SPEECH_REGION=eastus" >> .env
```

## Testing

Run the test script to verify functionality:

```bash
python test_transcription_switching.py
```

This will test:
- Service initialization
- Service switching
- API key validation
- Local model availability

## Error Handling

The implementation includes comprehensive error handling:

- **Service not available**: Clear error messages when services fail to initialize
- **API key missing**: Warnings when required API keys are not configured
- **Model loading failures**: Graceful fallbacks for local Whisper issues
- **Network errors**: Proper error reporting for cloud services

## Performance Considerations

### Local Whisper
- First-time model loading may take several minutes
- Subsequent loads are faster due to caching
- Consider using smaller models (tiny, base) for faster processing

### Cloud Services
- Network latency may affect transcription speed
- API rate limits may apply
- Costs scale with usage

## Future Enhancements

Potential improvements for future versions:

1. **Model Selection**: Allow users to choose Whisper model size
2. **Service Comparison**: Side-by-side accuracy comparison
3. **Batch Processing**: Support for multiple audio files
4. **Custom Models**: Integration with custom Whisper models
5. **Real-time Streaming**: Live transcription capabilities

## Troubleshooting

### Common Issues

1. **Local Whisper not loading**:
   - Ensure `openai-whisper` is installed: `pip install openai-whisper`
   - Check available disk space for model download
   - Verify internet connection for initial download

2. **API services not working**:
   - Verify API keys are correctly configured
   - Check environment variables or .env file
   - Ensure internet connectivity

3. **Service switching not working**:
   - Restart the application if issues persist
   - Check console logs for error messages
   - Verify backend components are properly initialized

### Debug Mode

Enable debug logging by setting the log level in the application configuration or by checking the console output for detailed error messages. 