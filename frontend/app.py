"""
Chainlit entry point — QR Accreditation Agent.
"""
import chainlit as cl

from agent.accreditation_agent import on_chat_start, on_message


@cl.on_chat_start
async def start():
    await on_chat_start()


@cl.on_message
async def message(msg: cl.Message):
    await on_message(msg)
